# vim: ts=4:sw=4:et:cc=120

from ace.analysis import RootAnalysis
from ace.system import ACESystemInterface, get_system

class AlertInterface(ACESystemInterface):
    def track_alert(root: str):
        raise NotImplementedError()

def track_alert(root: Union[RootAnalysis, str]):
    assert isinstance(root, str) or isinstance(root, RootAnalysis)
    if isinstance(root, RootAnalysis)
        root = root.uuid

    get_system().alert_tracking.track_alert(root)
