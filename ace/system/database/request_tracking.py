# vim: ts=4:sw=4:et:cc=120

import json
import datetime

from operator import itemgetter
from typing import Optional, Union

import ace

from ace.analysis import Observable, AnalysisModuleType
from ace.system.base import AnalysisRequestTrackingBaseInterface
from ace.system.database.schema import AnalysisRequestTracking, analysis_request_links
from ace.constants import TRACKING_STATUS_ANALYZING, EVENT_AR_EXPIRED
from ace.system.requests import AnalysisRequest
from ace.system.caching import generate_cache_key
from ace.exceptions import UnknownAnalysisModuleTypeError

from sqlalchemy import and_, text
from sqlalchemy.sql import delete, update, select
from sqlalchemy.orm import selectinload


class DatabaseAnalysisRequestTrackingInterface(AnalysisRequestTrackingBaseInterface):
    # if we switched to TRACKING_STATUS_ANALYZING then we start the expiration timer
    async def i_track_analysis_request(self, request: AnalysisRequest):
        # XXX we're using server-side time instead of database time
        expiration_date = None
        if request.status == TRACKING_STATUS_ANALYZING:
            expiration_date = datetime.datetime.now() + datetime.timedelta(request.type.timeout)

        db_request = AnalysisRequestTracking(
            id=request.id,
            expiration_date=expiration_date,
            analysis_module_type=request.type.name if request.type else None,
            cache_key=request.cache_key,
            root_uuid=request.root.uuid,
            json_data=request.to_json(),
        )

        async with self.get_db() as db:
            await db.merge(db_request)
            await db.commit()

    async def i_link_analysis_requests(self, source: AnalysisRequest, dest: AnalysisRequest) -> bool:
        from sqlalchemy import select, bindparam, String, and_

        # when we process an analysis request we "lock" it by setting the lock field
        # so if we try to link against an analysis request that is "locked" it fails

        # INSERT INTO analysis_request_links ( source_id, dest_id )
        # SELECT :source.id, :dest.id FROM analysis_tracking_request
        # WHERE source.id = :source.id AND lock IS NULL

        sel = select(
            bindparam("s", type_=String).label("source_id"),
            bindparam("d", type_=String).label("dest_id"),
        ).where(
            and_(AnalysisRequestTracking.id == source.id, AnalysisRequestTracking.lock == None)
        )  # noqa:E711
        update = analysis_request_links.insert().from_select(["source_id", "dest_id"], sel)
        async with self.get_db() as db:
            count = (await db.execute(update, {"s": source.id, "d": dest.id})).rowcount
            await db.commit()

        return count == 1

    async def i_get_linked_analysis_requests(self, source: AnalysisRequest) -> list[AnalysisRequest]:
        async with self.get_db() as db:
            source_request = (
                # NOTE you cannot do lazy loading with async in sqlalchemy 1.4
                (
                    await db.execute(
                        select(AnalysisRequestTracking)
                        .options(selectinload(AnalysisRequestTracking.linked_requests))
                        .where(AnalysisRequestTracking.id == source.id)
                    )
                ).one_or_none()
            )

            if source_request is None:
                return None

            # I think this is where you have to be careful with async
            return [AnalysisRequest.from_dict(json.loads(_.json_data), self) for _ in source_request[0].linked_requests]

    async def i_lock_analysis_request(self, request: AnalysisRequest) -> bool:
        async with self.get_db() as db:
            count = (
                await db.execute(
                    update(AnalysisRequestTracking)
                    .where(
                        and_(AnalysisRequestTracking.id == request.id, AnalysisRequestTracking.lock == None)
                    )  # noqa:E711
                    .values(lock=text("CURRENT_TIMESTAMP"))
                )
            ).rowcount
            await db.commit()

        return count == 1

    async def i_unlock_analysis_request(self, request: AnalysisRequest) -> bool:
        async with self.get_db() as db:
            count = (
                await db.execute(
                    update(AnalysisRequestTracking)
                    .where(
                        and_(AnalysisRequestTracking.id == request.id, AnalysisRequestTracking.lock != None)
                    )  # noqa:E711
                    .values(lock=None)
                )
            ).rowcount
            await db.commit()

        return count == 1

    async def i_delete_analysis_request(self, key: str) -> bool:
        async with self.get_db() as db:
            count = (
                await db.execute(delete(AnalysisRequestTracking).where(AnalysisRequestTracking.id == key))
            ).rowcount
            await db.commit()

        return count == 1

    async def i_get_expired_analysis_requests(self) -> list[AnalysisRequest]:
        async with self.get_db() as db:
            result = (
                await db.execute(
                    select(AnalysisRequestTracking).where(
                        datetime.datetime.now() > AnalysisRequestTracking.expiration_date
                    )
                )
            ).all()
            return [AnalysisRequest.from_dict(json.loads(_[0].json_data), self) for _ in result]

    # this is called when an analysis module type is removed (or expired)
    async def i_clear_tracking_by_analysis_module_type(self, amt: AnalysisModuleType):
        async with self.get_db() as db:
            await db.execute(
                delete(AnalysisRequestTracking).where(AnalysisRequestTracking.analysis_module_type == amt.name)
            )
            await db.commit()

    async def i_get_analysis_request_by_request_id(self, key: str) -> Union[AnalysisRequest, None]:
        async with self.get_db() as db:
            result = (
                await db.execute(select(AnalysisRequestTracking).where(AnalysisRequestTracking.id == key))
            ).one_or_none()

            if result is None:
                return None

            return AnalysisRequest.from_dict(json.loads(result[0].json_data), self)

    async def i_get_analysis_requests_by_root(self, key: str) -> list[AnalysisRequest]:
        async with self.get_db() as db:
            return [
                AnalysisRequest.from_dict(json.loads(_[0].json_data), self)
                for _ in (
                    await db.execute(select(AnalysisRequestTracking).where(AnalysisRequestTracking.root_uuid == key))
                ).all()
            ]

    async def i_get_analysis_request_by_cache_key(self, key: str) -> Union[AnalysisRequest, None]:
        assert isinstance(key, str)

        async with self.get_db() as db:
            result = (
                await db.execute(select(AnalysisRequestTracking).where(AnalysisRequestTracking.cache_key == key))
            ).one_or_none()

            if result is None:
                return None

            return AnalysisRequest.from_dict(json.loads(result[0].json_data), self)

    async def i_process_expired_analysis_requests(self, amt: AnalysisModuleType) -> int:
        assert isinstance(amt, AnalysisModuleType)
        async with self.get_db() as db:
            for db_request in await db.execute(
                select(AnalysisRequestTracking).where(
                    and_(
                        AnalysisRequestTracking.analysis_module_type == amt.name,
                        datetime.datetime.now() > AnalysisRequestTracking.expiration_date,
                    )
                )
            ):
                request = AnalysisRequest.from_json(db_request[0].json_data, self)
                await self.fire_event(EVENT_AR_EXPIRED, request)
                try:
                    await self.queue_analysis_request(request)
                except UnknownAnalysisModuleTypeError:
                    self.delete_analysis_request(request)
