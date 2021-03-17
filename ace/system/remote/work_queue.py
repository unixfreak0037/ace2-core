# vim: ts=4:sw=4:et:cc=120

from typing import Union, Optional

from ace.analysis import AnalysisModuleType
from ace.system.analysis_request import AnalysisRequest
from ace.system import ACESystem


class RemoteWorkQueueManagerInterface(ACESystem):
    async def get_next_analysis_request(
        self,
        owner_uuid: str,
        amt: Union[AnalysisModuleType, str],
        timeout: Optional[int] = 0,
        version: Optional[str] = None,
        extended_version: Optional[list[str]] = [],
    ) -> Union[AnalysisRequest, None]:
        return await self.get_api().get_next_analysis_request(owner_uuid, amt, timeout, version, extended_version)
