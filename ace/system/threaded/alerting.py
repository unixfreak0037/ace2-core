# vim: ts=4:sw=4:et:cc=120

import json
import queue
import threading

from typing import Union, Any, Optional

from ace.analysis import RootAnalysis
from ace.system.alerting import AlertTrackingInterface, UnknownAlertSystem


class ThreadedAlertTrackingInterface(AlertTrackingInterface):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.alert_systems = {}  # key = system name, value = queue.Queue(of RootAnalysis.uuid)
        self.sync_lock = threading.RLock()

    def register_alert_system(self, name: str) -> bool:
        with self.sync_lock:
            if name in self.alert_systems:
                return False

            self.alert_systems[name] = queue.Queue()
            return True

    def unregister_alert_system(self, name: str) -> bool:
        with self.sync_lock:
            return self.alert_systems.pop(name, None) is not None

    def submit_alert(self, root_uuid: str) -> bool:
        assert isinstance(root_uuid, str) and root_uuid

        result = False
        for name, queue in self.alert_systems.items():
            queue.put(root_uuid)
            result = True

        return result

    def get_alerts(self, name: str, timeout: Optional[int] = None) -> list[str]:
        assert isinstance(name, str) and str
        assert timeout is None or isinstance(timeout, int) and timeout >= 0
        result = []
        while True:
            try:
                if timeout is None:
                    result.append(self.alert_systems[name].get(block=False))
                else:
                    return [self.alert_systems[name].get(block=True, timeout=timeout)]
            except KeyError:
                raise UnknownAlertSystem(name)
            except queue.Empty:
                break

        return result

    def get_alert_count(self, name: str) -> int:
        assert isinstance(name, str) and str
        try:
            return self.alert_systems[name].qsize()
        except KeyError:
            raise UnknownAlertSystem(name)

    def reset(self):
        self.alert_systems = {}
