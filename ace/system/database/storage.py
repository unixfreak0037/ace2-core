# vim: ts=4:sw=4:et:cc=120

import datetime
import hashlib
import io
import json
import os
import os.path

from typing import Union, Iterator

from ace.data_model import ContentMetadata, CustomJSONEncoder
from ace.system import get_logger, get_system
from ace.system.config import get_config_value
from ace.system.database import get_db
from ace.system.database.schema import Storage, StorageRootTracking
from ace.system.storage import StorageInterface, store_content


class DatabaseStorageInterface(StorageInterface):
    """Abstract storage interface that uses a database to track file storage."""

    def get_content_meta(self, sha256: str) -> Union[ContentMetadata, None]:
        with get_db() as db:
            storage = db.query(Storage).filter(Storage.sha256 == sha256).one_or_none()
            if storage is None:
                return None

            return ContentMetadata(
                name=storage.name,
                sha256=sha256,
                size=storage.size,
                insert_date=storage.insert_date,
                roots=[_.root_uuid for _ in storage.roots],
                location=storage.location,
                expiration_date=storage.expiration_date,
                custom=json.loads(storage.custom),
            )

    def iter_expired_content(self) -> Iterator[ContentMetadata]:
        with get_db() as db:
            # XXX use db NOW()
            for storage in (
                db.query(Storage)
                .outerjoin(StorageRootTracking)
                .filter(
                    Storage.expiration_date != None,
                    datetime.datetime.now() >= Storage.expiration_date,
                    StorageRootTracking.sha256 == None,
                )
            ):
                yield ContentMetadata(
                    name=storage.name,
                    sha256=storage.sha256,
                    size=storage.size,
                    insert_date=storage.insert_date,
                    roots=[_.root_uuid for _ in storage.roots],
                    location=storage.location,
                    expiration_date=storage.expiration_date,
                    custom=json.loads(storage.custom),
                )

    def delete_content(self, sha256: str) -> bool:
        with get_db() as db:
            count = db.execute(Storage.__table__.delete().where(Storage.sha256 == sha256)).rowcount
            db.commit()

        file_path = self.get_file_path(sha256)
        if os.path.exists(file_path):
            os.remove(file_path)

        return count == 1

    def track_content_root(self, sha256: str, uuid: str):
        with get_db() as db:
            db.merge(StorageRootTracking(sha256=sha256, root_uuid=uuid))
            db.commit()
