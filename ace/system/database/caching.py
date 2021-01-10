# vim: ts=4:sw=4:et:cc=120

import datetime

from dataclasses import dataclass
from typing import Union, Optional

import ace

from ace.system.database import get_db
from ace.system.database.schema import AnalysisResultCache
from ace.system.caching import CachingInterface
from ace.system.analysis_request import AnalysisRequest
from ace.time import utc_now


class DatabaseCachingInterface(CachingInterface):
    def get_cached_analysis_result(self, cache_key: str) -> Union[AnalysisRequest, None]:
        result = get_db().query(AnalysisResultCache).filter(AnalysisResultCache.cache_key == cache_key).one_or_none()
        if result is None:
            return None

        if result.expiration_date is not None and utc_now() > result.expiration_date:
            return None

        return AnalysisRequest.from_json(result.json_data)

    def cache_analysis_result(self, cache_key: str, request: AnalysisRequest, expiration: Optional[int]) -> str:
        expiration_date = None
        # XXX using system side time
        if expiration is not None:
            expiration_date = utc_now() + datetime.timedelta(seconds=expiration)

        cache_result = AnalysisResultCache(
            cache_key=cache_key,
            expiration_date=expiration_date,
            json_data=request.to_json(),
        )

        get_db().merge(cache_result)
        get_db().commit()
        return cache_key
