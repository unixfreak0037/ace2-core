# vim: ts=4:sw=4:et:cc=120
#

from typing import Union, Any

from ace.analysis import RootAnalysis
from ace.system.base import AnalysisTrackingBaseInterface


class RemoteAnalysisTrackingInterface(AnalysisTrackingBaseInterface):
    async def i_get_root_analysis(self, uuid: str) -> Union[RootAnalysis, None]:
        return await self.get_api().get_root_analysis(uuid)

    async def i_get_analysis_details(self, uuid: str) -> Any:
        return await self.get_api().get_analysis_details(uuid)
