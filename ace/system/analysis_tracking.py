# vim: ts=4:sw=4:et:cc=120
#

import logging

from typing import Union, Any, Optional

from ace.analysis import RootAnalysis, Observable, Analysis
from ace.system import get_system, ACESystemInterface
from ace.system.locking import lock

class UnknownRootAnalysisError(ValueError):
    """Raised when there is an attempt to modify an unknown RootAnalysis object."""

    def __init__(self, uuid: str):
        super().__init__(f"unknown RootAnalysis {uuid}")


class AnalysisTrackingInterface(ACESystemInterface):
    def get_root_analysis(self, uuid: str) -> Union[dict, None]:
        """Returns the root for the given uuid or None if it does not exist.."""
        raise NotImplementedError()

    def track_root_analysis(self, uuid: str, root: dict):
        """Tracks the given root to the given RootAnalysis uuid."""
        raise NotImplementedError()

    def delete_root_analysis(self, uuid: str) -> bool:
        """Deletes the given RootAnalysis JSON data by uuid, and any associated analysis details."""
        raise NotImplementedError()

    def get_analysis_details(self, uuid: str) -> Any:
        """Returns the details for the given Analysis object, or None if is has not been set."""
        raise NotImplementedError()

    def track_analysis_details(self, root_uuid: str, uuid: str, value: Any):
        """Tracks the details for the given Analysis object (uuid) in the given root (root_uuid)."""
        raise NotImplementedError()

    def delete_analysis_details(self, uuid: str) -> bool:
        """Deletes the analysis details for the given Analysis referenced by id."""
        raise NotImplementedError()


def get_root_analysis(root: Union[RootAnalysis, str]) -> Union[RootAnalysis, None]:
    """Returns the loaded RootAnalysis for the given RootAnalysis or uuid, or None if it does not exist."""
    assert isinstance(root, RootAnalysis) or isinstance(root, str)

    if isinstance(root, RootAnalysis):
        root = root.uuid

    logging.debug(f"getting root analysis uuid {root}")
    root_dict = get_system().analysis_tracking.get_root_analysis(root)
    if root_dict is None:
        return None

    return RootAnalysis.from_dict(root_dict)


def track_root_analysis(root: RootAnalysis):
    assert isinstance(root, RootAnalysis)

    if root.uuid is None:
        raise ValueError(f"uuid property of {root} is None in track_root_analysis")

    logging.debug(f"tracking {root}")
    get_system().analysis_tracking.track_root_analysis(root.uuid, root.to_dict())


def delete_root_analysis(root: Union[RootAnalysis, str]) -> bool:
    assert isinstance(root, RootAnalysis) or isinstance(root, str)

    if isinstance(root, RootAnalysis):
        root = root.uuid

    logging.debug(f"deleting RootAnalysis with uuid {root}")
    return get_system().analysis_tracking.delete_root_analysis(root)


def get_analysis_details(uuid: str) -> Any:
    assert isinstance(uuid, str)

    logging.debug(f"loading analysis details {uuid}")
    return get_system().analysis_tracking.get_analysis_details(uuid)


def track_analysis_details(root: RootAnalysis, uuid: str, value: Any) -> bool:
    assert isinstance(root, RootAnalysis)
    assert isinstance(uuid, str)

    # we don't save Analysis that doesn't have the details set
    if value is None:
        return False

    logging.debug(f"tracking {root} analysis details {uuid}")
    get_system().analysis_tracking.track_analysis_details(root.uuid, uuid, value)
    return True


def delete_analysis_details(uuid: str) -> bool:
    assert isinstance(uuid, str)

    logging.debug(f"deleting analysis detqials {uuid}")
    return get_system().analysis_tracking.delete_analysis_details(uuid)
