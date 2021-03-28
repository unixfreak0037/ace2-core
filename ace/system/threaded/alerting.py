# vim: ts=4:sw=4:et:cc=120

import json
import queue
import threading

from typing import Union, Any, Optional

from ace.analysis import RootAnalysis
from ace.system.base import AlertingBaseInterface
from ace.exceptions import UnknownAlertSystemError


class ThreadedAlertTrackingInterface(AlertingBaseInterface):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.alert_systems = {}  # key = system name, value = queue.Queue(of RootAnalysis.uuid)
        self.alert_sync_lock = threading.RLock()

    async def i_register_alert_system(self, name: str) -> bool:
        with self.alert_sync_lock:
            if name in self.alert_systems:
                return False

            self.alert_systems[name] = queue.Queue()
            return True

    async def i_unregister_alert_system(self, name: str) -> bool:
        with self.alert_sync_lock:
            return self.alert_systems.pop(name, None) is not None

    async def i_submit_alert(self, root_uuid: str) -> bool:
        assert isinstance(root_uuid, str) and root_uuid

        result = False
        for name, work_queue in self.alert_systems.items():
            work_queue.put(root_uuid)
            result = True

        return result

    async def i_get_alerts(self, name: str, timeout: Optional[int] = None) -> list[str]:
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
                raise UnknownAlertSystemError(name)
            except queue.Empty:
                break

        return result

    async def i_get_alert_count(self, name: str) -> int:
        assert isinstance(name, str) and str
        try:
            return self.alert_systems[name].qsize()
        except KeyError:
            raise UnknownAlertSystemError(name)

    async def reset(self):
        await super().reset()
        self.alert_systems = {}
