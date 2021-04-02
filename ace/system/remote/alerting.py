# vim: ts=4:sw=4:et:cc=120

from typing import Optional, Union

from ace.analysis import RootAnalysis
from ace.system.base import AlertingBaseInterface


class RemoteAlertTrackingInterface(AlertingBaseInterface):
    async def register_alert_system(self, name: str) -> bool:
        return await self.get_api().register_alert_system(name)

    async def unregister_alert_system(self, name: str) -> bool:
        return await self.get_api().unregister_alert_system(name)

    async def get_alerts(self, name: str, timeout: Optional[int] = None) -> list[str]:
        return await self.get_api().get_alerts(name, timeout=timeout)

    async def submit_alert(self, root: Union[RootAnalysis, str]) -> bool:
        raise NotImplementedError()
