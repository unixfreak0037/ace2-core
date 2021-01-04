# vim: ts=4:sw=4:et:cc=120

import json
from typing import Union, Any

from ace.analysis import RootAnalysis
from ace.system.alerting import AlertTrackingInterface


class ThreadedAlertTrackingInterface(AlertTrackingInterface):

    alerts = {}  # key = uuid, value = RootAnalysis.to_json()

    def track_alert(self, root: RootAnalysis) -> Any:
        assert isinstance(root, RootAnalysis)
        self.alerts[root.uuid] = root.to_json()
        return root.uuid

    def get_alert(self, id: str) -> Union[Any, None]:
        assert isinstance(id, str)
        result = self.alerts.get(id, None)
        if not result:
            return None

        return RootAnalysis.from_json(result)

    def reset(self):
        self.alerts = {}
