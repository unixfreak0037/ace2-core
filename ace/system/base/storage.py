# vim: ts=4:sw=4:et:cc=120
#
#
#

import collections.abc
import hashlib
import io

from pathlib import Path
from typing import Union, Optional, AsyncGenerator, Iterator

from ace import coreapi
from ace.analysis import RootAnalysis
from ace.constants import *
from ace.crypto import iter_encrypt_stream, iter_decrypt_stream
from ace.data_model import ContentMetadata
from ace.logging import get_logger

import aiofiles

CONFIG_STORAGE_ENCRYPTION_ENABLED = "/core/storage/encrypted"


# utility class used to compute sha256 and size of data as it is being read
class MetaComputation:
    def __init__(self):
        self.m = hashlib.sha256()
        self.size = 0

    @property
    def sha256(self):
        return self.m.hexdigest().lower()


class StorageBaseInterface:
    async def storage_encryption_enabled(self) -> bool:
        """Returns True if encryption is configured and storage is configured to be encrypted."""
        # the settings need to be configured
        if self.encryption_settings is None:
            return False

        # and the key needs to be loaded
        if self.encryption_settings.aes_key is None:
            return False

        # and this needs to return True
        return await self.get_config_value(CONFIG_STORAGE_ENCRYPTION_ENABLED, False)

    @coreapi
    async def store_content(
        self,
        content: Union[
            bytes, str, io.BytesIO, aiofiles.threadpool.binary.AsyncBufferedReader, AsyncGenerator[bytes, None]
        ],
        meta: ContentMetadata,
    ) -> str:
        assert (
            isinstance(content, bytes)
            or isinstance(content, str)
            or isinstance(content, io.BytesIO)
            or isinstance(content, aiofiles.threadpool.binary.AsyncBufferedReader)
            or isinstance(content, AsyncGenerator)
        )
        assert isinstance(meta, ContentMetadata)
        get_logger().debug(f"storing content {meta}")

        if isinstance(content, bytes):
            source = io.BytesIO(content)
        elif isinstance(content, str):
            source = io.BytesIO(content.encode())
        elif isinstance(content, io.BytesIO):
            source = content
        elif isinstance(content, aiofiles.threadpool.binary.AsyncBufferedReader):
            source = content
        elif isinstance(content, AsyncGenerator):
            source = content
        else:
            raise TypeError(
                "store_content only accepts bytes, str, io.BytesIO, "
                "aiofiles.threadpool.binary.AsyncBufferedIOBase or AsyncGenerator"
            )

        meta_computation = MetaComputation()

        async def _reader(target) -> AsyncGenerator[bytes, None]:
            async def _read() -> bytes:
                if isinstance(target, io.BytesIO):
                    return target.read(io.DEFAULT_BUFFER_SIZE)
                elif isinstance(target, AsyncGenerator):
                    try:
                        return await target.__anext__()
                    except StopAsyncIteration:
                        return None
                else:
                    return await target.read(io.DEFAULT_BUFFER_SIZE)

            while True:
                chunk = await _read()
                if not chunk:
                    break

                meta_computation.size += len(chunk)
                meta_computation.m.update(chunk)
                yield chunk

        source = _reader(source)

        if await self.storage_encryption_enabled():
            # if storage encryption is enabled then the source_content becomes
            # the *output* of the encryption process
            source = iter_encrypt_stream(self.encryption_settings.aes_key, source)

        sha256 = await self.i_store_content(source, meta_computation, meta)
        await self.fire_event(EVENT_STORAGE_NEW, [sha256, meta])
        return sha256

    async def i_store_content(
        self, source: AsyncGenerator[bytes, None], meta_computation: MetaComputation, meta: ContentMetadata
    ) -> str:
        """Stores the content and returns the key needed to lookup the content.

        Args:
            source: an AsyncGenerator that yields chunks of the bytes to store
            meta_computation: a ComputingAsyncGenerator that contains the sha256 and size of the data
            after all of the data is read from source
            meta: the meta data of the source

        Returns:
            the sha256 hash of the content of source
        """
        raise NotImplementedError()

    @coreapi
    async def get_content_bytes(self, sha256: str) -> Union[bytes, None]:
        _buffer = io.BytesIO()
        async for chunk in await self.iter_content(sha256):
            if chunk is None:
                return None

            _buffer.write(chunk)

        return _buffer.getvalue()

    # async def i_get_content_bytes(self, sha256: str) -> Union[bytes, None]:
    # """Returns the requested stored content as a bytes object, or None if the content does not exist."""
    # raise NotImplementedError()

    @coreapi
    async def iter_content(
        self, sha256: str, buffer_size: Optional[int] = io.DEFAULT_BUFFER_SIZE
    ) -> Union[AsyncGenerator[bytes, None], None]:

        if await self.storage_encryption_enabled():
            return iter_decrypt_stream(self.encryption_settings.aes_key, self.i_iter_content(sha256, buffer_size))
        else:
            return self.i_iter_content(sha256, buffer_size)

    async def i_iter_content(self, sha256: str, buffer_size: int) -> Union[AsyncGenerator[bytes, None], None]:
        raise NotImplementedError()

    @coreapi
    async def load_file(self, sha256: str, path: str) -> Union[ContentMetadata, None]:
        return await self.i_load_file(sha256, path)

    async def i_load_file(self, sha256: str, path: str) -> Union[ContentMetadata, None]:
        """Saves the content of the given file into path and returns the
        metadata.  The purpose of this function is to transfer the content into
        the target file in the most efficient way possible."""
        raise NotImplementedError()

    @coreapi
    async def save_file(self, path: str, **kwargs) -> Union[str, None]:
        return await self.i_save_file(path, **kwargs)

    async def i_save_file(self, path: str, **kwargs) -> Union[str, None]:
        """Stores the contents of the given file and returns the sha256 hash.
        The purpose of this function is to transfer the content from the target
        file in the most efficient way possible."""
        raise NotImplementedError()

    @coreapi
    async def get_content_meta(self, sha256: str) -> Union[ContentMetadata, None]:
        return await self.i_get_content_meta(sha256)

    async def i_get_content_meta(self, sha256: str) -> Union[ContentMetadata, None]:
        """Returns the meta data of the stored content, or None if the content does not exist."""
        raise NotImplementedError()

    @coreapi
    async def iter_expired_content(self) -> Iterator[ContentMetadata]:
        """Returns an iterator for all the expired content."""
        return self.i_iter_expired_content()

    async def i_iter_expired_content(self) -> Iterator[ContentMetadata]:
        """Iterates over expired content metadata."""
        raise NotImplementedError()

    @coreapi
    async def delete_content(self, sha256: str) -> bool:
        get_logger().debug(f"deleting content {sha256}")
        result = await self.i_delete_content(sha256)
        if result:
            await self.fire_event(EVENT_STORAGE_DELETED, sha256)

        return result

    async def i_delete_content(self, sha256: str) -> bool:
        """Deletes the given content. Returns True if content was actually deleted."""
        raise NotImplementedError()

    @coreapi
    async def track_content_root(self, sha256: str, root: Union[RootAnalysis, str]):
        assert isinstance(sha256, str)
        assert isinstance(root, RootAnalysis) or isinstance(root, str)

        if isinstance(root, RootAnalysis):
            root = root.uuid

        get_logger().debug(f"tracking content {sha256} to root {root}")
        await self.i_track_content_root(sha256, root)

    async def i_track_content_root(self, sha256: str, uuid: str):
        """Associates stored content to a root analysis."""
        raise NotImplementedError()

    @coreapi
    async def has_valid_root_reference(self, meta: ContentMetadata) -> bool:
        """Returns True if the given meta has a valid (existing) RootAnalysis reference."""
        for root_uuid in meta.roots:
            if await self.get_root_analysis(root_uuid) is not None:
                return True

        return False

    @coreapi
    async def delete_expired_content(self) -> int:
        """Deletes all expired content and returns the number of items deleted."""
        get_logger().debug("deleting expired content")
        count = 0
        async for meta in await self.iter_expired_content():
            root_exists = False
            for root_uuid in meta.roots:
                if await self.analyis_tracking.get_root_analysis(root_uuid) is not None:
                    root_exists = True
                    break

            if root_exists:
                continue

            if await self.delete_content(meta.sha256):
                count += 1

        return count
