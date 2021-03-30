# vim: ts=4:sw=4:et:cc=120

from typing import Union

from ace.analysis import AnalysisModuleType, Observable
from ace.system.base import AnalysisRequestTrackingBaseInterface
from ace.system.base.request_tracking import AnalysisRequest


class RemoteAnalysisRequestTrackingInterface(AnalysisRequestTrackingBaseInterface):
    async def process_analysis_request(self, ar: AnalysisRequest):
        return await self.get_api().process_analysis_request(ar)

    async def track_analysis_request(self, request: AnalysisRequest):
        raise NotImplementedError()

    async def lock_analysis_request(self, request: AnalysisRequest) -> bool:
        raise NotImplementedError()

    async def unlock_analysis_request(self, request: AnalysisRequest) -> bool:
        raise NotImplementedError()

    async def link_analysis_requests(self, source_request: AnalysisRequest, dest_request: AnalysisRequest) -> bool:
        raise NotImplementedError()

    async def get_linked_analysis_requests(self, source_request: AnalysisRequest) -> list[AnalysisRequest]:
        raise NotImplementedError()

    async def delete_analysis_request(self, target: Union[AnalysisRequest, str]) -> bool:
        raise NotImplementedError()

    async def get_expired_analysis_requests(self) -> list[AnalysisRequest]:
        raise NotImplementedError()

    async def get_analysis_request(self, key: str) -> Union[AnalysisRequest, None]:
        raise NotImplementedError()

    async def get_analysis_request_by_request_id(self, request_id: str) -> Union[AnalysisRequest, None]:
        raise NotImplementedError()

    async def get_analysis_request_by_observable(
        self, observable: Observable, amt: AnalysisModuleType
    ) -> Union[AnalysisRequest, None]:
        raise NotImplementedError()

    async def get_analysis_requests_by_root(self, key: str) -> list[AnalysisRequest]:
        raise NotImplementedError()

    async def clear_tracking_by_analysis_module_type(self, amt: AnalysisModuleType):
        raise NotImplementedError()

    async def process_expired_analysis_requests(self, amt: AnalysisModuleType):
        raise NotImplementedError()

    async def queue_analysis_request(self, ar: AnalysisRequest):
        raise NotImplementedError()
