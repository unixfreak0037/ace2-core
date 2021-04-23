# vim: ts=4:sw=4:et:cc=120
#

from typing import Union, Any

from ace.analysis import RootAnalysis
from ace.system.base import AnalysisTrackingBaseInterface


class RemoteAnalysisTrackingInterface(AnalysisTrackingBaseInterface):
    async def i_get_root_analysis(self, uuid: str) -> Union[RootAnalysis, None]:
        return await self.get_api().get_root_analysis(uuid)

    async def get_analysis_details(self, uuid: str) -> Any:
        return await self.get_api().get_analysis_details(uuid)

    async def track_root_analysis(self, root: RootAnalysis) -> bool:
        raise NotImplementedError()

    async def update_root_analysis(self, root: RootAnalysis) -> bool:
        raise NotImplementedError()

    async def delete_root_analysis(self, root: Union[RootAnalysis, str]) -> bool:
        raise NotImplementedError()

    async def root_analysis_exists(self, root: Union[RootAnalysis, str]) -> bool:
        raise NotImplementedError()

    async def track_analysis_details(self, root: RootAnalysis, uuid: str, value: Any) -> bool:
        raise NotImplementedError()

    async def delete_analysis_details(self, uuid: str) -> bool:
        raise NotImplementedError()

    async def analysis_details_exists(self, uuid: str) -> bool:
        raise NotImplementedError()
