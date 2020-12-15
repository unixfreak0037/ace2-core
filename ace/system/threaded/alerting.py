# vim: ts=4:sw=4:et:cc=120

import json
from typing import Union, Any

from ace.analysis import RootAnalysis
from ace.json import JSONEncoder
from ace.system.alerting import AlertTrackingInterface

class ThreadedAlertTrackingInterface(AlertTrackingInterface):

    alerts = {} # key = uuid, value = RootAnalysis

    def track_alert(self, root: dict):
        assert isinstance(root, dict)
        self.alerts[root[RootAnalysis.KEY_UUID]] = json.dumps(root, cls=JSONEncoder)

    def get_alert(self, id: str) -> Union[Any, None]:
        assert isinstance(id, str)
        result = self.alerts.get(id, None)
        if not result:
            return None

        return RootAnalysis.from_dict(json.loads(result))

    def reset(self):
        self.alerts = {}
