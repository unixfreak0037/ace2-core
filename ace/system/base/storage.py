# vim: ts=4:sw=4:et:cc=120
#
#
#

import io

from typing import Union, Optional, AsyncGenerator, Iterator

from ace import coreapi
from ace.data_model import ContentMetadata
from ace.constants import *
from ace.analysis import RootAnalysis
from ace.logging import get_logger


class StorageBaseInterface:
    @coreapi
    async def store_content(self, content: Union[bytes, str, io.IOBase], meta: ContentMetadata) -> str:
        assert isinstance(content, bytes) or isinstance(content, str) or isinstance(content, io.IOBase)
        assert isinstance(meta, ContentMetadata)
        get_logger().debug(f"storing content {meta}")
        sha256 = await self.i_store_content(content, meta)
        await self.fire_event(EVENT_STORAGE_NEW, [sha256, meta])
        return sha256

    async def i_store_content(self, content: Union[bytes, str, io.IOBase], meta: ContentMetadata) -> str:
        """Stores the content with the given meta data and returns the key needed to lookup the content.

        Args:
            content: the content to store
            meta: metadata about the content

        Returns:
            the lookup key for the content (sha256 hash)
        """
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
    async def get_content_bytes(self, sha256: str) -> Union[bytes, None]:
        return await self.i_get_content_bytes(sha256)

    async def i_get_content_bytes(self, sha256: str) -> Union[bytes, None]:
        """Returns the requested stored content as a bytes object, or None if the content does not exist."""
        raise NotImplementedError()

    @coreapi
    async def iter_content(
        self, sha256: str, buffer_size: Optional[int] = io.DEFAULT_BUFFER_SIZE
    ) -> Union[AsyncGenerator[bytes, None], None]:
        async for _buffer in self.i_iter_content(sha256, buffer_size):
            yield _buffer

    async def i_iter_content(self, sha256: str, buffer_size: int) -> Union[AsyncGenerator[bytes, None], None]:
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
