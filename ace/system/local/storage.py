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

from ace.constants import ACE_STORAGE_ROOT
from ace.data_model import ContentMetadata, CustomJSONEncoder
from ace.exceptions import UnknownFileError
from ace.logging import get_logger
from ace.system.base.storage import MetaComputation
from ace.system.database.schema import Storage, StorageRootTracking
from ace.system.database.storage import DatabaseStorageInterface

import aiofiles
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import insert


class LocalStorageInterface(DatabaseStorageInterface):
    """Storage interface that stores files in the local file system."""

    def __init__(self, *args, storage_root=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.storage_root = storage_root

        if not self.storage_root:
            if ACE_STORAGE_ROOT in os.environ:
                self.storage_root = os.environ[ACE_STORAGE_ROOT]

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
        sub_dir = os.path.join(self.storage_root, file_name[0:3])
        if not await asyncio.get_running_loop().run_in_executor(None, os.path.isdir, sub_dir):
            await asyncio.get_running_loop().run_in_executor(None, os.mkdir, sub_dir)

        return os.path.join(sub_dir, file_name)

    async def i_store_content(
        self,
        source: AsyncGenerator[bytes, None],
        meta_computation: MetaComputation,
        meta: ContentMetadata,
    ) -> str:
        assert isinstance(source, AsyncGenerator)
        assert isinstance(meta_computation, MetaComputation)
        assert isinstance(meta, ContentMetadata)

        file_path = await self.initialize_file_path()

        async with aiofiles.open(file_path, "wb") as fp:
            async for chunk in source:
                await fp.write(chunk)

        meta.sha256 = meta_computation.sha256
        meta.size = meta_computation.size
        meta.location = file_path

        try:
            async with self.get_db() as db:
                await db.execute(
                    insert(Storage).values(
                        sha256=meta.sha256,
                        name=meta.name,
                        size=meta.size,
                        location=file_path,  # full path
                        expiration_date=meta.expiration_date,
                        custom=json.dumps(meta.custom, cls=CustomJSONEncoder),
                    )
                )
                await db.commit()
        except IntegrityError:
            get_logger().warning(f"file with sha256 {meta.sha256} already exists")
            try:
                # XXX async
                os.remove(file_path)
            except Exception as e:
                get_logger().exception(f"unable to remove duplicate file {file_path}")

            return meta.sha256

        get_logger().info(f"stored file content {meta.name} {meta.sha256} at {file_path}")
        return meta.sha256

    async def i_save_file(self, path, **kwargs) -> Union[str, None]:
        assert isinstance(path, str) and path
        meta = ContentMetadata(name=os.path.basename(path), **kwargs)
        async with aiofiles.open(path, "rb") as fp:
            await self.store_content(fp, meta)

        return meta.sha256

    async def i_iter_content(self, sha256: str, buffer_size: int) -> Union[AsyncGenerator[bytes, None], None]:
        try:
            file_path = await self.get_file_path(sha256)
            if file_path is None:
                raise UnknownFileError()

            async with aiofiles.open(await self.get_file_path(sha256), "rb") as fp:
                while True:
                    data = await fp.read(buffer_size)
                    if data == b"":
                        break

                    yield data

        except IOError as e:
            get_logger().warning(f"unable to get content stream for {sha256}: {e}")
            raise e

    async def i_load_file(self, sha256: str, path: str) -> Union[ContentMetadata, None]:
        meta = await self.get_content_meta(sha256)
        if meta is None:
            raise UnknownFileError()

        # if storage encryption is NOT enabled then we have an option to "copy" the data super fast
        # on systems that support hard links
        if not await self.storage_encryption_enabled():
            try:
                # fastest way to "copy" data is to just create a new link to it
                src_path = os.path.join(self.storage_root, meta.location)
                await asyncio.get_running_loop().run_in_executor(None, os.link, src_path, path)
                get_logger().debug(f"hard linked {src_path} to {path}")
                return meta
            except IOError:
                pass

        # NOTE in theory it makes sense fall back to symlinks but there are two problems with that
        # 1) you're referencing the actual file
        # 2) external tooling and analysis may not work or get invalid results if the file is a symlink

        # if that didn't work then we just do a byte-for-byte copy as normal
        # this also works if the data is encrypted
        async with aiofiles.open(path, "wb") as fp:
            async for chunk in await self.iter_content(sha256):
                await fp.write(chunk)

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
