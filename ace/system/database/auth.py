# vim: ts=4:sw=4:et:cc=120

import hashlib
import uuid

from typing import Optional, Union

from ace.api import ApiKey
from ace.system.base import AuthenticationBaseInterface
from ace.system.database.schema import ApiKey as ApiKeyDbModel
from ace.exceptions import DuplicateApiKeyNameError

from sqlalchemy import and_
from sqlalchemy.sql import select, delete
import sqlalchemy.exc


def _sha256(data: str) -> str:
    m = hashlib.sha256()
    m.update(data.encode())
    return m.hexdigest()


class DatabaseAuthenticationInterface(AuthenticationBaseInterface):
    async def i_create_api_key(
        self, name: str, description: Optional[str] = None, is_admin: Optional[bool] = False
    ) -> Union[ApiKey, None]:
        api_key = str(uuid.uuid4())
        async with self.get_db() as db:
            try:
                db.add(ApiKeyDbModel(api_key=_sha256(api_key), name=name, description=description, is_admin=is_admin))
                await db.commit()
            except sqlalchemy.exc.IntegrityError:
                raise DuplicateApiKeyNameError()

        return ApiKey(api_key=api_key, name=name, description=description, is_admin=is_admin)

    async def i_delete_api_key(self, name: str) -> bool:
        async with self.get_db() as db:
            row_count = (await db.execute(delete(ApiKeyDbModel).where(ApiKeyDbModel.name == name))).rowcount
            await db.commit()
            return row_count == 1

    async def i_verify_api_key(self, api_key: str, is_admin: Optional[bool] = False) -> bool:
        async with self.get_db() as db:
            condition = ApiKeyDbModel.api_key == _sha256(api_key)
            if is_admin:
                condition = and_(condition, ApiKeyDbModel.is_admin == True)  # noqa:E712

            if (await db.execute(select(ApiKeyDbModel).where(condition))).one_or_none():
                return True
            else:
                return False

    async def i_get_api_keys(self) -> list[ApiKey]:
        async with self.get_db() as db:
            result = []
            async for _ in await db.execute(select(ApiKeyDbModel)):
                result.append(ApiKey(api_key=_.api_key, name=_.name, description=_.description, is_admin=_.is_admin))

            return result
