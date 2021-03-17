# vim: ts=4:sw=4:et:cc=120

from typing import Optional

from ace.system import ACESystem


class RemoteAlertTrackingInterface(ACESystem):
    async def register_alert_system(self, name: str) -> bool:
        return await self.get_api().register_alert_system(name)

    async def unregister_alert_system(self, name: str) -> bool:
        return await self.get_api().unregister_alert_system(name)

    async def get_alerts(self, name: str, timeout: Optional[int] = None) -> list[str]:
        return await self.get_api().get_alerts(name, timeout=timeout)
