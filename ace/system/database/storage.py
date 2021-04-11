# vim: ts=4:sw=4:et:cc=120

import datetime
import hashlib
import io
import json
import os
import os.path

from typing import Union, Iterator

from ace.data_model import ContentMetadata, CustomJSONEncoder
from ace.logging import get_logger
from ace.system.base import StorageBaseInterface
from ace.system.database.schema import Storage, StorageRootTracking

from sqlalchemy.sql import select, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError


class DatabaseStorageInterface(StorageBaseInterface):
    """Abstract storage interface that uses a database to track file storage."""

    async def i_get_content_meta(self, sha256: str) -> Union[ContentMetadata, None]:
        async with self.get_db() as db:
            storage = (
                await db.execute(select(Storage).options(selectinload(Storage.roots)).where(Storage.sha256 == sha256))
            ).one_or_none()
            if storage is None:
                return None

            storage = storage[0]
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

    async def i_iter_expired_content(self) -> Iterator[ContentMetadata]:
        async with self.get_db() as db:
            # XXX use db NOW()
            for (storage,) in await db.execute(
                select(Storage)
                .options(selectinload(Storage.roots))
                .outerjoin(StorageRootTracking)
                .where(
                    Storage.expiration_date != None,  # noqa: E711
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

    async def i_track_content_root(self, sha256: str, uuid: str):
        try:
            async with self.get_db() as db:
                await db.merge(StorageRootTracking(sha256=sha256, root_uuid=uuid))
                await db.commit()
        except IntegrityError as e:
            get_logger().warning("unable to track roots for {uuid}: {e}")

    async def i_delete_content(self, sha256: str) -> bool:
        async with self.get_db() as db:
            count = (await db.execute(delete(Storage).where(Storage.sha256 == sha256))).rowcount
            await db.commit()

        return count == 1
