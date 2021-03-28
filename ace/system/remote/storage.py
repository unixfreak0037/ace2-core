# vim: ts=4:sw=4:et:cc=120

import os.path
import io

from typing import Union, AsyncGenerator

from ace.data_model import ContentMetadata
from ace.system.base import StorageBaseInterface


class RemoteStorageInterface(StorageBaseInterface):
    async def store_content(self, content: Union[bytes, str, io.IOBase], meta: ContentMetadata) -> str:
        return await self.get_api().store_content(content, meta)

    async def i_load_file(self, sha256: str, path: str) -> Union[ContentMetadata, None]:
        return await self.get_api().load_file(sha256, path)

    async def get_content_bytes(self, sha256: str) -> Union[bytes, None]:
        return await self.get_api().get_content_bytes(sha256)

    async def i_iter_content(self, sha256: str, buffer_size: int) -> Union[AsyncGenerator[bytes, None], None]:
        async for data in self.get_api().iter_content(sha256, buffer_size):
            if data:
                yield data

    async def i_save_file(self, path: str, **kwargs) -> Union[str, None]:
        return await self.get_api().save_file(path, **kwargs)

    async def get_content_meta(self, sha256: str) -> Union[ContentMetadata, None]:
        return await self.get_api().get_content_meta(sha256)
