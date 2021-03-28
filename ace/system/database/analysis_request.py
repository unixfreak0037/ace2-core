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
from ace.system.analysis_request import AnalysisRequest
from ace.system.caching import generate_cache_key
from ace.exceptions import UnknownAnalysisModuleTypeError

from sqlalchemy import and_, text


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

        with self.get_db() as db:
            db.merge(db_request)
            db.commit()

    async def i_link_analysis_requests(self, source: AnalysisRequest, dest: AnalysisRequest) -> bool:
        from sqlalchemy import select, bindparam, String, and_

        # when we process an analysis request we "lock" it by setting the lock field
        # so if we try to link against an analysis request that is "locked" it fails

        sel = select(
            [bindparam("s", type_=String).label("source_id"), bindparam("d", type_=String).label("dest_id")],
            AnalysisRequestTracking.__table__,
        ).where(and_(AnalysisRequestTracking.id == source.id, AnalysisRequestTracking.lock == None))
        update = analysis_request_links.insert().from_select(["source_id", "dest_id"], sel)
        with self.get_db() as db:
            count = db.execute(update, {"s": source.id, "d": dest.id}).rowcount
            db.commit()

        return count == 1

    async def i_get_linked_analysis_requests(self, source: AnalysisRequest) -> list[AnalysisRequest]:
        with self.get_db() as db:
            source_request = (
                db.query(AnalysisRequestTracking).filter(AnalysisRequestTracking.id == source.id).one_or_none()
            )

            if source_request is None:
                return None

            return [AnalysisRequest.from_dict(json.loads(_.json_data), self) for _ in source_request.linked_requests]

    async def i_lock_analysis_request(self, request: AnalysisRequest) -> bool:
        with self.get_db() as db:
            count = db.execute(
                AnalysisRequestTracking.__table__.update()
                .where(and_(AnalysisRequestTracking.id == request.id, AnalysisRequestTracking.lock == None))
                .values(lock=text("CURRENT_TIMESTAMP"))
            ).rowcount
            db.commit()

        return count == 1

    async def i_unlock_analysis_request(self, request: AnalysisRequest) -> bool:
        with self.get_db() as db:
            count = db.execute(
                AnalysisRequestTracking.__table__.update()
                .where(and_(AnalysisRequestTracking.id == request.id, AnalysisRequestTracking.lock != None))
                .values(lock=None)
            ).rowcount
            db.commit()

        return count == 1

    async def i_delete_analysis_request(self, key: str) -> bool:
        with self.get_db() as db:
            count = db.execute(
                AnalysisRequestTracking.__table__.delete().where(AnalysisRequestTracking.id == key)
            ).rowcount
            db.commit()

        return count == 1

    async def i_get_expired_analysis_requests(self) -> list[AnalysisRequest]:
        with self.get_db() as db:
            result = (
                db.query(AnalysisRequestTracking)
                .filter(datetime.datetime.now() > AnalysisRequestTracking.expiration_date)
                .all()
            )
            return [AnalysisRequest.from_dict(json.loads(_.json_data), self) for _ in result]

    # this is called when an analysis module type is removed (or expired)
    async def i_clear_tracking_by_analysis_module_type(self, amt: AnalysisModuleType):
        with self.get_db() as db:
            db.execute(
                AnalysisRequestTracking.__table__.delete().where(
                    AnalysisRequestTracking.analysis_module_type == amt.name
                )
            )
            db.commit()

    async def i_get_analysis_request_by_request_id(self, key: str) -> Union[AnalysisRequest, None]:
        with self.get_db() as db:
            result = db.query(AnalysisRequestTracking).filter(AnalysisRequestTracking.id == key).one_or_none()

            if result is None:
                return None

            return AnalysisRequest.from_dict(json.loads(result.json_data), self)

    async def i_get_analysis_requests_by_root(self, key: str) -> list[AnalysisRequest]:
        with self.get_db() as db:
            return [
                AnalysisRequest.from_dict(json.loads(_.json_data), self)
                for _ in db.query(AnalysisRequestTracking).filter(AnalysisRequestTracking.root_uuid == key).all()
            ]

    async def i_get_analysis_request_by_cache_key(self, key: str) -> Union[AnalysisRequest, None]:
        assert isinstance(key, str)

        with self.get_db() as db:
            result = db.query(AnalysisRequestTracking).filter(AnalysisRequestTracking.cache_key == key).one_or_none()

            if result is None:
                return None

            return AnalysisRequest.from_dict(json.loads(result.json_data), self)

    async def i_process_expired_analysis_requests(self, amt: AnalysisModuleType) -> int:
        assert isinstance(amt, AnalysisModuleType)
        with self.get_db() as db:
            for db_request in db.query(AnalysisRequestTracking).filter(
                and_(
                    AnalysisRequestTracking.analysis_module_type == amt.name,
                    datetime.datetime.now() > AnalysisRequestTracking.expiration_date,
                )
            ):
                request = AnalysisRequest.from_json(db_request.json_data, self)
                await self.fire_event(EVENT_AR_EXPIRED, request)
                try:
                    await self.submit_analysis_request(request)
                except UnknownAnalysisModuleTypeError:
                    self.delete_analysis_request(request)
