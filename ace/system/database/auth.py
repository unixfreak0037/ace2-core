# vim: ts=4:sw=4:et:cc=120

import hashlib
import uuid

from typing import Optional, Union

from ace.system import ACESystem
from ace.system.database.schema import ApiKey
from ace.system.exceptions import DuplicateApiKeyNameError

import sqlalchemy.exc


def _sha256(data: str) -> str:
    m = hashlib.sha256()
    m.update(data.encode())
    return m.hexdigest()


class DatabaseAuthenticationInterface(ACESystem):
    async def i_create_api_key(self, name: str, description: Optional[str] = None) -> Union[str, None]:
        api_key = str(uuid.uuid4())
        with self.get_db() as db:
            try:
                db.add(ApiKey(api_key=_sha256(api_key), name=name, description=description))
                db.commit()
            except sqlalchemy.exc.IntegrityError:
                raise DuplicateApiKeyNameError()

        return api_key

    async def i_delete_api_key(self, name: str) -> bool:
        with self.get_db() as db:
            row_count = db.execute(ApiKey.__table__.delete().where(ApiKey.name == name)).rowcount
            db.commit()
            return row_count == 1

    async def i_verify_api_key(self, api_key: str) -> bool:
        with self.get_db() as db:
            if db.query(ApiKey).filter(ApiKey.api_key == _sha256(api_key)).one_or_none():
                return True
            else:
                return False
