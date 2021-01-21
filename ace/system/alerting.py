# vim: ts=4:sw=4:et:cc=120
#

import logging

from typing import Union, Any

from ace.analysis import RootAnalysis
from ace.system import ACESystemInterface, get_system
from ace.system.analysis_tracking import get_root_analysis


class AlertTrackingInterface(ACESystemInterface):
    """Tracks alerts as they are detected during the processing of analysis requests."""

    def track_alert(self, root: RootAnalysis) -> Any:
        raise NotImplementedError()


def track_alert(root: Union[RootAnalysis, str]) -> Any:
    """Tracks the given root analysis object as an alert."""
    assert isinstance(root, str) or isinstance(root, RootAnalysis)
    if isinstance(root, str):
        root = get_root_analysis(root)

    logging.info(f"tracking alert {root}")
    return get_system().alerting.track_alert(root)
