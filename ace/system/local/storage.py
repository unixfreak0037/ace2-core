# vim: ts=4:sw=4:et:cc=120

import asyncio
import datetime
import hashlib
import io
import json
import os
import os.path
import uuid

from pathlib import Path
from typing import Union, Iterator, AsyncGenerator

from ace.data_model import ContentMetadata, CustomJSONEncoder
from ace.logging import get_logger
from ace.system.database.schema import Storage, StorageRootTracking
from ace.system.database.storage import DatabaseStorageInterface

import aiofiles
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import insert

CONFIG_DB_FILE_STORAGE_ROOT = "/ace/core/storage/path"


class LocalStorageInterface(DatabaseStorageInterface):
    """Storage interface that stores files in the local file system."""

    async def get_storage_root(self):
        """Returns the full path to the storage root directory."""
        return await self.get_config_value(CONFIG_DB_FILE_STORAGE_ROOT, self.storage_root, "ACE_STORAGE_ROOT")

    async def get_file_path(self, sha256: str) -> str:
        """Returns the full path to the local path that should be used to store
        the file with the given sha256 hash."""
        assert isinstance(sha256, str) and sha256
        meta = await self.get_content_meta(sha256)
        if meta is None:
            return None

        return meta.location

    async def initialize_file_path(self) -> str:
        """Initializes a file path for storage of a file. Returns the full path
        to the target file."""
        file_name = str(uuid.uuid4())
        sub_dir = os.path.join(await self.get_storage_root(), file_name[0:3])
        if not await asyncio.get_running_loop().run_in_executor(None, os.path.isdir, sub_dir):
            await asyncio.get_running_loop().run_in_executor(None, os.mkdir, sub_dir)

        return os.path.join(sub_dir, file_name)

    async def i_store_content(
        self,
        content: Union[bytes, str, io.IOBase, aiofiles.threadpool.binary.AsyncBufferedReader, Path],
        meta: ContentMetadata,
    ) -> str:
        file_path = await self.initialize_file_path()
        m = hashlib.sha256()
        size = 0

        async with aiofiles.open(file_path, "wb") as fp:
            if isinstance(content, str):
                data = content.encode()
                await fp.write(data)
                m.update(data)
                size = len(data)

            elif isinstance(content, io.IOBase):
                while True:
                    _buffer = content.read(io.DEFAULT_BUFFER_SIZE)
                    if not _buffer:
                        break

                    m.update(_buffer)
                    size += len(_buffer)
                    await fp.write(_buffer)

            elif isinstance(content, Path):
                async with aiofiles.open(str(content), "rb") as content:
                    while True:
                        _buffer = await content.read(io.DEFAULT_BUFFER_SIZE)
                        if not _buffer:
                            break

                        m.update(_buffer)
                        size += len(_buffer)
                        await fp.write(_buffer)

            elif isinstance(content, aiofiles.threadpool.binary.AsyncBufferedReader):
                while True:
                    _buffer = await content.read(io.DEFAULT_BUFFER_SIZE)
                    if not _buffer:
                        break

                    m.update(_buffer)
                    size += len(_buffer)
                    await fp.write(_buffer)

            elif isinstance(content, bytes):
                await fp.write(content)
                m.update(content)
                size = len(content)
            else:
                raise TypeError(f"unsupported content type {type(content)}")

        sha256 = m.hexdigest().lower()
        meta.size = size
        meta.sha256 = sha256

        try:
            async with self.get_db() as db:
                await db.execute(
                    insert(Storage).values(
                        sha256=sha256,
                        name=meta.name,
                        size=meta.size,
                        location=file_path,  # full path
                        expiration_date=meta.expiration_date,
                        custom=json.dumps(meta.custom, cls=CustomJSONEncoder),
                    )
                )
                await db.commit()
        except IntegrityError:
            get_logger().warning(f"file with sha256 {sha256} already exists")
            try:
                os.remove(file_path)
            except Exception as e:
                get_logger().exception(f"unable to remove duplicate file {file_path}")

            return sha256

        get_logger().info(f"stored file content {meta.name} {sha256} at {file_path}")
        return sha256

    async def i_save_file(self, path, **kwargs) -> Union[str, None]:
        assert isinstance(path, str) and path
        meta = ContentMetadata(name=os.path.basename(path), **kwargs)
        async with aiofiles.open(path, "rb") as fp:
            await self.store_content(fp, meta)

        return meta.sha256

    async def i_get_content_bytes(self, sha256: str) -> Union[bytes, None]:
        try:
            file_path = await self.get_file_path(sha256)
            if not file_path:
                return None

            async with aiofiles.open(await self.get_file_path(sha256), "rb") as fp:
                return await fp.read()
        except IOError as e:
            get_logger().debug(f"unable to get content bytes for {sha256}: {e}")
            return None

    async def i_iter_content(self, sha256: str, buffer_size: int) -> Union[AsyncGenerator[bytes, None], None]:
        try:
            file_path = await self.get_file_path(sha256)
            if file_path is None:
                yield None
            else:
                async with aiofiles.open(await self.get_file_path(sha256), "rb") as fp:
                    while True:
                        data = await fp.read(buffer_size)
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
            src_path = os.path.join(await self.get_storage_root(), meta.location)
            await asyncio.get_running_loop().run_in_executor(None, os.link, src_path, path)
        except IOError:
            # otherwise we have to actually make a copy
            src_path = os.path.join(await self.get_storage_root(), meta.location)
            await asyncio.get_running_loop().run_in_executor(None, os.copy, src_path, path)

        return meta

    async def i_delete_content(self, sha256: str) -> bool:
        file_path = await self.get_file_path(sha256)
        try:
            if await asyncio.get_running_loop().run_in_executor(os.path.exists, file_path):
                await asyncio.get_running_loop().run_in_executor(os.remove, file_path)
        except Exception as e:
            get_logger().exception(f"unable to delete {file_path}")

        if not await DatabaseStorageInterface.i_delete_content(self, sha256):
            return False

        return True
