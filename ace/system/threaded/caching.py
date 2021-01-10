# vim: ts=4:sw=4:et:cc=120

import datetime
import json
import threading

from dataclasses import dataclass
from typing import Union, Optional

from ace.analysis import AnalysisModuleType
from ace.system.caching import CachingInterface
from ace.system.analysis_request import AnalysisRequest
from ace.time import utc_now


@dataclass
class CachedAnalysisResult:
    request: str
    expiration: datetime.datetime = None


class ThreadedCachingInterface(CachingInterface):

    cache = {}  # key = generate_cache_key(), value = CachedAnalysisResult
    cache_by_amt = {}  # key = AnalysisModuleType.name, value = [ keys ]
    sync_lock = threading.RLock()

    def get_cached_analysis_result(self, cache_key: str) -> Union[AnalysisRequest, None]:
        try:
            with self.sync_lock:
                cached_analysis = self.cache[cache_key]
                if cached_analysis.expiration and utc_now() >= cached_analysis.expiration:
                    # del self.cache[cache_key]
                    # self.cache_by_amt.pop(cache_key, None)
                    return None

            return AnalysisRequest.from_json(cached_analysis.request)

        except KeyError:
            return None

    def cache_analysis_result(self, cache_key: str, request: AnalysisRequest, expiration: Optional[int]) -> str:
        cached_result = CachedAnalysisResult(request.to_json())
        if expiration is not None:
            cached_result.expiration = utc_now() + datetime.timedelta(seconds=expiration)

        with self.sync_lock:
            self.cache[cache_key] = cached_result
            if request.type.name not in self.cache_by_amt:
                self.cache_by_amt[request.type.name] = []

            self.cache_by_amt[request.type.name].append(cache_key)

        return cache_key

    def delete_expired_cached_analysis_results(self):
        with self.sync_lock:
            target_list = []
            for key, car in self.cache.items():
                if utc_now() >= car.expiration:
                    target_list.append(key)

            for key in target_list:
                target = AnalysisRequest.from_json(self.cache[key].request)
                del self.cache[key]
                try:
                    self.cache_by_amt[target.type.name].remove(key)
                except ValueError:
                    pass

    def delete_cached_analysis_results_by_module_type(self, amt: AnalysisModuleType):
        with self.sync_lock:
            target_list = self.cache_by_amt.pop(amt.name, None)
            if not target_list:
                return

            for target in target_list:
                self.cache.pop(target, None)

    def get_total_cache_size(self, amt: Optional[AnalysisModuleType] = None) -> int:
        if amt:
            with self.sync_lock:
                try:
                    return len(self.cache_by_amt[amt.name])
                except KeyError:
                    return 0
        else:
            with self.sync_lock:
                return len(self.cache)

    def reset(self):
        self.cache = {}
        self.cache_by_amt = {}
