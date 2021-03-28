# vim: ts=4:sw=4:et:cc=120
#
#
#

from typing import Optional, Union

from ace import coreapi
from ace.analysis import RootAnalysis
from ace.constants import EVENT_ALERT_SYSTEM_REGISTERED, EVENT_ALERT_SYSTEM_UNREGISTERED, EVENT_ALERT
from ace.logging import get_logger


class AlertingBaseInterface:
    @coreapi
    async def register_alert_system(self, name: str) -> bool:
        assert isinstance(name, str) and name
        result = await self.i_register_alert_system(name)
        if result:
            await self.fire_event(EVENT_ALERT_SYSTEM_REGISTERED, name)

        return result

    async def i_register_alert_system(self, name: str) -> bool:
        raise NotImplementedError()

    @coreapi
    async def unregister_alert_system(self, name: str) -> bool:
        assert isinstance(name, str) and name
        result = await self.i_unregister_alert_system(name)
        if result:
            await self.fire_event(EVENT_ALERT_SYSTEM_UNREGISTERED, name)

        return result

    async def i_unregister_alert_system(self, name: str) -> bool:
        raise NotImplementedError()

    @coreapi
    async def submit_alert(self, root: Union[RootAnalysis, str]) -> bool:
        """Submits the given RootAnalysis uuid as an alert to any registered alert systems.
        Returns True if at least one system is registered, False otherwise."""
        assert isinstance(root, str) or isinstance(root, RootAnalysis)
        if isinstance(root, RootAnalysis):
            root = root.uuid

        get_logger().info(f"submitting alert {root}")
        result = await self.i_submit_alert(root)
        if result:
            await self.fire_event(EVENT_ALERT, root)

        return result

    async def i_submit_alert(self, root_uuid: str) -> bool:
        raise NotImplementedError()

    @coreapi
    async def get_alerts(self, name: str, timeout: Optional[int] = None) -> list[str]:
        assert isinstance(name, str) and name
        return await self.i_get_alerts(name, timeout)

    async def i_get_alerts(self, name: str, timeout: Optional[int] = None) -> list[str]:
        raise NotImplementedError()

    #
    # alerting instrumentation
    #

    @coreapi
    async def get_alert_count(self, name: str) -> int:
        """Returns the number of alerts outstanding for the given registered alert system."""
        assert isinstance(name, str) and name
        return await self.i_get_alert_count(name)

    async def i_get_alert_count(self, name: str) -> int:
        raise NotImplementedError()
