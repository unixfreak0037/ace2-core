# vim: ts=4:sw=4:et:cc=120

from typing import Union, Optional

from ace.analysis import AnalysisModuleType
from ace.system.requests import AnalysisRequest
from ace.system.base import WorkQueueBaseInterface


class RemoteWorkQueueManagerInterface(WorkQueueBaseInterface):
    async def get_next_analysis_request(
        self,
        owner_uuid: str,
        amt: Union[AnalysisModuleType, str],
        timeout: Optional[int] = 0,
        version: Optional[str] = None,
        extended_version: Optional[list[str]] = [],
    ) -> Union[AnalysisRequest, None]:
        return await self.get_api().get_next_analysis_request(owner_uuid, amt, timeout, version, extended_version)

    async def delete_work_queue(self, amt: Union[AnalysisModuleType, str]) -> bool:
        raise NotImplementedError()

    async def add_work_queue(self, amt: Union[AnalysisModuleType, str]) -> bool:
        raise NotImplementedError()

    async def put_work(self, amt: Union[AnalysisModuleType, str], analysis_request: AnalysisRequest):
        raise NotImplementedError()

    async def get_work(self, amt: Union[AnalysisModuleType, str], timeout: int) -> Union[AnalysisRequest, None]:
        raise NotImplementedError()

    async def get_queue_size(self, amt: Union[AnalysisModuleType, str]) -> int:
        raise NotImplementedError()
