# vim: ts=4:sw=4:et:cc=120
#

from typing import Union, Any, Optional

from ace.analysis import RootAnalysis
from ace.system import ACESystemInterface, get_system, get_logger
from ace.system.analysis_tracking import get_root_analysis
from ace.system.constants import EVENT_ALERT, EVENT_ALERT_SYSTEM_REGISTERED, EVENT_ALERT_SYSTEM_UNREGISTERED
from ace.system.events import fire_event


class UnknownAlertSystem(KeyError):
    pass


class AlertTrackingInterface(ACESystemInterface):
    """Tracks alerts as they are detected during the processing of analysis requests."""

    def register_alert_system(self, name: str) -> bool:
        raise NotImplementedError()

    def unregister_alert_system(self, name: str) -> bool:
        raise NotImplementedError()

    def submit_alert(self, root_uuid: str) -> bool:
        """Submits the given RootAnalysis uuid as an alert to any registered alert systems.
        Returns True if at least one system is registered, False otherwise."""
        raise NotImplementedError()

    def get_alerts(self, name: str, timeout: Optional[int] = None) -> list[str]:
        raise NotImplementedError()

    #
    # instrumentation
    #

    def get_alert_count(self, name: str) -> int:
        """Returns the number of alerts outstanding for the given registered alert system."""
        raise NotImplementedError()


def register_alert_system(name: str) -> bool:
    assert isinstance(name, str) and name
    result = get_system().alerting.register_alert_system(name)
    if result:
        fire_event(EVENT_ALERT_SYSTEM_REGISTERED, name)

    return result


def unregister_alert_system(name: str) -> bool:
    assert isinstance(name, str) and name
    result = get_system().alerting.unregister_alert_system(name)
    if result:
        fire_event(EVENT_ALERT_SYSTEM_UNREGISTERED, name)

    return result


def submit_alert(root: Union[RootAnalysis, str]) -> bool:
    """Tracks the given root analysis object as an alert."""
    assert isinstance(root, str) or isinstance(root, RootAnalysis)
    if isinstance(root, RootAnalysis):
        root = root.uuid

    get_logger().info(f"submitting alert {root}")
    result = get_system().alerting.submit_alert(root)
    if result:
        fire_event(EVENT_ALERT, root)

    return result


def get_alerts(name: str, timeout: Optional[int] = None) -> list[str]:
    assert isinstance(name, str) and name
    return get_system().alerting.get_alerts(name, timeout)


def get_alert_count(name: str) -> int:
    assert isinstance(name, str) and name
    return get_system().alerting.get_alert_count(name)
