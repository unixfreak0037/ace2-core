# vim: ts=4:sw=4:et:cc=120
#

from typing import Union, Any

from ace.analysis import RootAnalysis
from ace.system import ACESystemInterface, get_system
from ace.system.analysis_tracking import get_root_analysis


class AlertTrackingInterface(ACESystemInterface):
    """Tracks alerts as they are detected during the processing of analysis requests."""

    def track_alert(self, root: dict):
        raise NotImplementedError()

    def get_alert(self, id: str) -> Union[Any, None]:
        raise NotImplementedError()


def track_alert(root: Union[RootAnalysis, str]):
    """Tracks the given root analysis object as an alert."""
    assert isinstance(root, str) or isinstance(root, RootAnalysis)
    if isinstance(root, str):
        root = get_root_analysis(root)

    get_system().alerting.track_alert(root.to_dict())


def get_alert(root: Union[RootAnalysis, str]) -> Union[Any, None]:
    """Returns an object representing an alert for the given root object."""
    assert isinstance(root, RootAnalysis) or isinstance(root, str)
    if isinstance(root, RootAnalysis):
        root = root.uuid

    return get_system().alerting.get_alert(root)
