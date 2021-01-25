# vim: ts=4:sw=4:et:cc=120

import json

from dataclasses import dataclass, field
from typing import Union, List, Optional, Any

from ace.analysis import RootAnalysis, Observable, Analysis
from ace.system.analysis_tracking import AnalysisTrackingInterface, UnknownRootAnalysisError
from ace.system.analysis_module import AnalysisModuleType
from ace.system.exceptions import *


@dataclass
class RootAnalysisTracking:
    root: str
    details: List[str] = field(default_factory=list)


class ThreadedAnalysisTrackingInterface(AnalysisTrackingInterface):

    root_analysis = {}  # key = RootAnalysis.uuid, value = RootAnalysisTracking
    analysis_details = {}  # key = Analysis.uuid, value = Any

    def track_root_analysis(self, root: RootAnalysis):
        assert isinstance(root, RootAnalysis)
        self.root_analysis[root.uuid] = RootAnalysisTracking(root=root.to_json(exclude_analysis_details=True))

    def get_root_analysis(self, uuid: str) -> Union[RootAnalysis, None]:
        try:
            tracking = self.root_analysis[uuid]
        except KeyError:
            return None

        return RootAnalysis.from_json(tracking.root)

    def delete_root_analysis(self, uuid: str) -> bool:
        root_tracking = self.root_analysis.pop(uuid, None)
        if not root_tracking:
            return False

        for analysis_uuid in root_tracking.details:
            self.delete_analysis_details(analysis_uuid)

        return True

    def root_analysis_exists(self, uuid: str) -> bool:
        return uuid in self.root_analysis

    def get_analysis_details(self, uuid: dict) -> Any:
        details_json = self.analysis_details.get(uuid)
        if details_json is None:
            return None

        return json.loads(details_json)

    def track_analysis_details(self, root_uuid: str, uuid: str, value):
        try:
            self.root_analysis[root_uuid].details.append(uuid)
        except KeyError:
            raise UnknownRootAnalysisError(root_uuid)

        self.analysis_details[uuid] = json.dumps(value)

    def delete_analysis_details(self, uuid: str) -> bool:
        return self.analysis_details.pop(uuid, None) is not None

    def analysis_details_exists(self, uuid: str) -> bool:
        return uuid in self.analysis_details

    def reset(self):
        self.root_analysis = {}
        self.analysis_details = {}
