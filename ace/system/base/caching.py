# vim: ts=4:sw=4:et:cc=120
#
#
#

from typing import Union, Optional

from ace import coreapi
from ace.analysis import AnalysisModuleType, Observable
from ace.constants import *
from ace.logging import get_logger
from ace.system.requests import AnalysisRequest
from ace.system.caching import generate_cache_key


class CachingBaseInterface:
    @coreapi
    async def get_cached_analysis_result(
        self, observable: Observable, amt: AnalysisModuleType
    ) -> Union[AnalysisRequest, None]:
        cache_key = generate_cache_key(observable, amt)
        if cache_key is None:
            return None

        return await self.i_get_cached_analysis_result(cache_key)

    async def i_get_cached_analysis_result(self, cache_key: str) -> Union[AnalysisRequest, None]:
        """Returns the cached AnalysisRequest for the analysis with the given cache key, or None if it does not exist."""
        raise NotImplementedError()

    @coreapi
    async def cache_analysis_result(self, request: AnalysisRequest) -> Union[str, None]:
        assert isinstance(request, AnalysisRequest)
        assert request.is_observable_analysis_result

        cache_key = generate_cache_key(request.observable, request.type)
        if cache_key is None:
            return None

        get_logger().debug(f"caching analysis request {request} with key {cache_key} ttl {request.type.cache_ttl}")
        result = await self.i_cache_analysis_result(cache_key, request, request.type.cache_ttl)
        await self.fire_event(EVENT_CACHE_NEW, [cache_key, request])
        return result

    async def i_cache_analysis_result(self, cache_key: str, request: AnalysisRequest, expiration: Optional[int]) -> str:
        """Caches the AnalysisRequest to the cache key and returns the cache id."""
        raise NotImplementedError()

    @coreapi
    async def delete_expired_cached_analysis_results(self):
        get_logger().debug("deleting expired cached analysis results")
        await self.i_delete_expired_cached_analysis_results()

    async def i_delete_expired_cached_analysis_results(self):
        """Deletes all cache results that have expired."""
        raise NotImplementedError()

    @coreapi
    async def delete_cached_analysis_results_by_module_type(self, amt: AnalysisModuleType):
        get_logger().debug(f"deleting cached analysis results for analysis module type {amt}")
        await self.i_delete_cached_analysis_results_by_module_type(amt)

    async def i_delete_cached_analysis_results_by_module_type(self, amt: AnalysisModuleType):
        """Deletes all cache results for the given type."""
        raise NotImplementedError()

    #
    # instrumentation
    #

    @coreapi
    async def get_cache_size(self, amt: Optional[AnalysisModuleType] = None):
        return await self.i_get_cache_size(amt)

    async def i_get_cache_size(self, amt: Optional[AnalysisModuleType] = None) -> int:
        """Returns the total number of cached results. If no type is specified
        then the total size of all cached results are returned.  Otherwise the
        total size of all cached results for the given type are returned."""
        raise NotImplementedError()
