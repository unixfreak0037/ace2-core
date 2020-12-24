# vim: ts=4:sw=4:et:cc=120

import json
import datetime

from operator import itemgetter
from typing import Optional, Union

import ace

from ace.analysis import Observable
from ace.json import JSONEncoder
from ace.database.schema import AnalysisRequestTracking
from ace.system.constants import *
from ace.system.analysis_request import AnalysisRequestTrackingInterface, AnalysisRequest
from ace.system.analysis_module import AnalysisModuleType
from ace.system.caching import generate_cache_key


class DatabaseAnalysisRequestTrackingInterface(AnalysisRequestTrackingInterface):
    # if we switched to TRACKING_STATUS_ANALYZING then we start the expiration timer
    def track_analysis_request(self, request: AnalysisRequest):
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
            json_data=json.dumps(request, cls=JSONEncoder, sort_keys=True),
        )

        ace.db.merge(db_request)
        ace.db.commit()

    def link_analysis_requests(self, source: AnalysisRequest, dest: AnalysisRequest):
        source_request = ace.db.query(AnalysisRequestTracking).filter(AnalysisRequestTracking.id == source.id).one_or_none()
        if source_request is None:
            return

        dest_request = ace.db.query(AnalysisRequestTracking).filter(AnalysisRequestTracking.id == dest.id).one_or_none()
        if dest_request is None:
            return

        source_request.linked_requests.append(dest_request)
        ace.db.commit()

    def get_linked_analysis_requests(self, source: AnalysisRequest) -> list[AnalysisRequest]:
        source_request = ace.db.query(AnalysisRequestTracking).filter(AnalysisRequestTracking.id == source.id).one_or_none()
        if source_request is None:
            return None

        return [AnalysisRequest.from_dict(json.loads(_.json_data)) for _ in source_request.linked_requests]

    def delete_analysis_request(self, key: str) -> bool:
        ace.db.execute(AnalysisRequestTracking.__table__.delete().where(AnalysisRequestTracking.id == key))
        ace.db.commit()
        # TODO return correct result
        return True

    def get_expired_analysis_requests(self) -> list[AnalysisRequest]:
        result = (
            ace.db.query(AnalysisRequestTracking)
            .filter(datetime.datetime.now() > AnalysisRequestTracking.expiration_date)
            .all()
        )
        return [AnalysisRequest.from_dict(json.loads(_.json_data)) for _ in result]

    # this is called when an analysis module type is removed (or expired)
    def clear_tracking_by_analysis_module_type(self, amt: AnalysisModuleType):
        raise NotImplementedError()

    def get_analysis_request_by_request_id(self, key: str) -> Union[AnalysisRequest, None]:
        result = ace.db.query(AnalysisRequestTracking).filter(AnalysisRequestTracking.id == key).one_or_none()
        if result is None:
            return None

        return AnalysisRequest.from_dict(json.loads(result.json_data))

    def get_analysis_requests_by_root(self, key: str) -> list[AnalysisRequest]:
        return [
            AnalysisRequest.from_dict(json.loads(_.json_data))
            for _ in ace.db.query(AnalysisRequestTracking).filter(AnalysisRequestTracking.root_uuid == key).all()
        ]

    def get_analysis_request_by_cache_key(self, key: str) -> Union[AnalysisRequest, None]:
        assert isinstance(key, str)

        result = ace.db.query(AnalysisRequestTracking).filter(AnalysisRequestTracking.cache_key == key).one_or_none()
        if result is None:
            return None

        return AnalysisRequest.from_dict(json.loads(result.json_data))
