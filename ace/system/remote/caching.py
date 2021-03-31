# vim: ts=4:sw=4:et:cc=120
#

from typing import Union, Optional

from ace.analysis import Observable, AnalysisModuleType
from ace.system.requests import AnalysisRequest
from ace.system.base import CachingBaseInterface


class RemoteCachingInterface(CachingBaseInterface):
    async def get_cached_analysis_result(
        self, observable: Observable, amt: AnalysisModuleType
    ) -> Union[AnalysisRequest, None]:
        raise NotImplementedError()

    async def cache_analysis_result(self, request: AnalysisRequest) -> Union[str, None]:
        raise NotImplementedError()

    async def delete_expired_cached_analysis_results(self):
        raise NotImplementedError()

    async def delete_cached_analysis_results_by_module_type(self, amt: AnalysisModuleType):
        raise NotImplementedError()

    async def get_cache_size(self, amt: Optional[AnalysisModuleType] = None):
        raise NotImplementedError()
