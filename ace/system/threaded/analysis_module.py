# vim: ts=4:sw=4:et:cc=120

from typing import Union, List

from ace.analysis import AnalysisModuleType
from ace.system.analysis_module import AnalysisModuleTrackingInterface, AnalysisModuleType


class ThreadedAnalysisModuleTrackingInterface(AnalysisModuleTrackingInterface):

    amt_tracking = {}  # key = str, value = AnalysisModuleType.to_json()

    def track_analysis_module_type(self, amt: AnalysisModuleType):
        self.amt_tracking[amt.name] = amt.to_json()

    def delete_analysis_module_type(self, amt: AnalysisModuleType):
        self.amt_tracking.pop(amt.name, None)

    def get_analysis_module_type(self, name: str) -> Union[AnalysisModuleType, None]:
        json_data = self.amt_tracking.get(name)
        if not json_data:
            return None

        return AnalysisModuleType.from_json(json_data)

    def get_all_analysis_module_types(self) -> list[AnalysisModuleType]:
        return [AnalysisModuleType.from_json(_) if _ else None for _ in self.amt_tracking.values()]

    def reset(self):
        self.amt_tracking = {}
