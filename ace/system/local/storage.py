# vim: ts=4:sw=4:et:cc=120

import datetime
import hashlib
import io
import json
import os
import os.path

from typing import Union, Iterator, AsyncGenerator

from ace.data_model import ContentMetadata, CustomJSONEncoder
from ace.logging import get_logger
from ace.system.database.schema import Storage, StorageRootTracking
from ace.system.database.storage import DatabaseStorageInterface

CONFIG_DB_FILE_STORAGE_ROOT = "/ace/core/storage/path"


class LocalStorageInterface(DatabaseStorageInterface):
    """Storage interface that stores files in the local file system."""

    async def get_storage_root(self):
        """Returns the full path to the storage root directory."""
        return await self.get_config_value(CONFIG_DB_FILE_STORAGE_ROOT, self.storage_root, "ACE_STORAGE_ROOT")

    async def get_file_path(self, sha256: str) -> str:
        """Returns the local path that should be used to store the file with the given sha256 hash."""
        assert isinstance(sha256, str) and sha256
        return os.path.join(await self.get_storage_root(), sha256[0:3], sha256)

    async def initialize_file_path(self, sha256: str) -> str:
        """Initializes a file path for storage of a file. Returns the full path to the target file."""
        assert isinstance(sha256, str) and sha256
        sub_dir = os.path.join(await self.get_storage_root(), sha256[0:3])
        if not os.path.isdir(sub_dir):
            os.mkdir(sub_dir)

        return os.path.join(sub_dir, sha256)

    #
    # XXX avoid loading file into memory
    #

    async def i_store_content(self, content: Union[bytes, str, io.IOBase], meta: ContentMetadata) -> str:
        if isinstance(content, str):
            data = content.encode()
        elif isinstance(content, io.IOBase):
            # TODO calculate sha2 as we go
            data = io.BytesIO()
            while True:
                _buffer = content.read(io.DEFAULT_BUFFER_SIZE)
                if not _buffer:
                    break

                data.write(_buffer)

            data = data.getvalue()
        elif isinstance(content, bytes):
            data = content
        else:
            raise TypeError(f"unsupported content type {type(content)}")

        m = hashlib.sha256()
        m.update(data)
        sha256 = m.hexdigest().lower()

        meta.size = len(data)
        meta.sha256 = sha256

        # generate a file path based on the sha256 hash
        file_path = await self.initialize_file_path(sha256)

        if os.path.exists(file_path):
            get_logger().warning(f"{file_path} already exists")

        # XXX use fcntl here
        with open(file_path, "wb") as fp:
            fp.write(data)

        get_logger().info(f"stored file content {meta.name} {sha256} at {file_path}")

        async with self.get_db() as db:
            await db.merge(
                Storage(
                    sha256=sha256,
                    name=meta.name,
                    size=meta.size,
                    location=file_path,
                    expiration_date=meta.expiration_date,
                    custom=json.dumps(meta.custom, cls=CustomJSONEncoder),
                )
            )
            await db.commit()

        return sha256

    async def i_save_file(self, path, **kwargs) -> Union[str, None]:
        assert isinstance(path, str) and path
        meta = ContentMetadata(name=os.path.basename(path), **kwargs)
        with open(path, "rb") as fp:
            await self.store_content(fp, meta)

        return meta.sha256

    async def i_get_content_bytes(self, sha256: str) -> Union[bytes, None]:
        try:
            with open(await self.get_file_path(sha256), "rb") as fp:
                return fp.read()
        except IOError as e:
            get_logger().debug(f"unable to get content bytes for {sha256}: {e}")
            return None

    async def i_iter_content(self, sha256: str, buffer_size: int) -> Union[AsyncGenerator[bytes, None], None]:
        try:
            with open(await self.get_file_path(sha256), "rb") as fp:
                while True:
                    data = fp.read(buffer_size)
                    if data == b"":
                        break

                    yield data

        except IOError as e:
            get_logger().warning(f"unable to get content stream for {sha256}: {e}")
            yield None

    async def i_load_file(self, sha256: str, path: str) -> Union[ContentMetadata, None]:
        meta = await self.get_content_meta(sha256)
        if meta is None:
            return None

        try:
            # fastest way to "copy" data is to just create a new link to it
            os.link(meta.location, path)
        except IOError:
            # otherwise we have to actually make a copy
            os.copy(meta.location, path)

        return meta

    async def i_delete_content(self, sha256: str) -> bool:
        if not await DatabaseStorageInterface.i_delete_content(self, sha256):
            return False

        file_path = await self.get_file_path(sha256)
        if os.path.exists(file_path):
            os.remove(file_path)

        return True
