# vim: ts=4:sw=4:et:cc=120

from typing import Union

from ace.analysis import AnalysisModuleType
from ace.system.base import AnalysisModuleTrackingBaseInterface


class RemoteAnalysisModuleTrackingInterface(AnalysisModuleTrackingBaseInterface):
    async def register_analysis_module_type(self, amt: AnalysisModuleType) -> AnalysisModuleType:
        return await self.get_api().register_analysis_module_type(amt)

    async def i_get_analysis_module_type(self, name: str) -> Union[AnalysisModuleType, None]:
        return await self.get_api().get_analysis_module_type(name)

    async def track_analysis_module_type(self, amt: AnalysisModuleType):
        raise NotImplementedError()

    async def delete_analysis_module_type(self, amt: Union[AnalysisModuleType, str]) -> bool:
        raise NotImplementedError()

    async def get_all_analysis_module_types(self) -> list[AnalysisModuleType]:
        raise NotImplementedError()
