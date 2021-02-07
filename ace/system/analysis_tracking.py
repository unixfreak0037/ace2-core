# vim: ts=4:sw=4:et:cc=120
#

import logging
import uuid

from typing import Union, Any, Optional

from ace.analysis import RootAnalysis, Observable, Analysis
from ace.system import get_system, ACESystemInterface
from ace.system.constants import (
    EVENT_ANALYSIS_ROOT_NEW,
    EVENT_ANALYSIS_ROOT_MODIFIED,
    EVENT_ANALYSIS_ROOT_DELETED,
    EVENT_ANALYSIS_DETAILS_NEW,
    EVENT_ANALYSIS_DETAILS_MODIFIED,
    EVENT_ANALYSIS_DETAILS_DELETED,
)
from ace.system.events import fire_event


class UnknownRootAnalysisError(ValueError):
    """Raised when there is an attempt to modify an unknown RootAnalysis object."""

    def __init__(self, uuid: str):
        super().__init__(f"unknown RootAnalysis {uuid}")


class AnalysisTrackingInterface(ACESystemInterface):
    def get_root_analysis(self, uuid: str) -> Union[RootAnalysis, None]:
        """Returns the root for the given uuid or None if it does not exist.."""
        raise NotImplementedError()

    def track_root_analysis(self, root: RootAnalysis) -> bool:
        """Tracks the root analysis, returns True if it worked. Updates the
        version property of the root."""
        raise NotImplementedError()

    def update_root_analysis(self, root: RootAnalysis) -> bool:
        """Updates the root. Returns True if the update was successful, False
        otherwise. Updates the version property of the root.

        The version of the root passed in must match the version on record for
        the update to work."""
        raise NotImplementedError()

    def delete_root_analysis(self, uuid: str) -> bool:
        """Deletes the given RootAnalysis JSON data by uuid, and any associated analysis details."""
        raise NotImplementedError()

    def root_analysis_exists(self, uuid: str) -> bool:
        """Returns True if the given root analysis exists, False otherwise."""
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

    def analysis_details_exists(self, uuid: str) -> bool:
        """Returns True if the given analysis details exist, False otherwise."""
        raise NotImplementedError()


def get_root_analysis(root: Union[RootAnalysis, str]) -> Union[RootAnalysis, None]:
    """Returns the loaded RootAnalysis for the given RootAnalysis or uuid, or None if it does not exist."""
    assert isinstance(root, RootAnalysis) or isinstance(root, str)

    if isinstance(root, RootAnalysis):
        root = root.uuid

    logging.debug(f"getting root analysis uuid {root}")
    return get_system().analysis_tracking.get_root_analysis(root)


def track_root_analysis(root: RootAnalysis) -> bool:
    """Inserts or updates the root analysis. Returns True if either operation is successfull."""
    assert isinstance(root, RootAnalysis)
    from ace.system.storage import track_content_root

    if root.uuid is None:
        raise ValueError(f"uuid property of {root} is None in track_root_analysis")

    logging.debug(f"tracking root {root}")
    if not get_system().analysis_tracking.track_root_analysis(root):
        return update_root_analysis(root)

    # make sure storage content is tracked to their roots
    for observable in root.get_observables_by_type("file"):
        track_content_root(observable.value, root)

    fire_event(EVENT_ANALYSIS_ROOT_NEW, root)
    return True


def update_root_analysis(root: RootAnalysis) -> bool:
    assert isinstance(root, RootAnalysis)
    from ace.system.storage import track_content_root

    if root.uuid is None:
        raise ValueError(f"uuid property of {root} is None in update_root_analysis")

    logging.debug(f"updating root {root} with version {root.version}")
    if not get_system().analysis_tracking.update_root_analysis(root):
        return False

    # make sure storage content is tracked to their roots
    for observable in root.get_observables_by_type("file"):
        track_content_root(observable.value, root)

    fire_event(EVENT_ANALYSIS_ROOT_MODIFIED, root)
    return True


def delete_root_analysis(root: Union[RootAnalysis, str]) -> bool:
    assert isinstance(root, RootAnalysis) or isinstance(root, str)

    if isinstance(root, RootAnalysis):
        root = root.uuid

    logging.debug(f"deleting root {root}")
    result = get_system().analysis_tracking.delete_root_analysis(root)
    if result:
        fire_event(EVENT_ANALYSIS_ROOT_DELETED, root)

    return result


def root_analysis_exists(root: Union[RootAnalysis, str]) -> bool:
    assert isinstance(root, RootAnalysis) or isinstance(root, str)

    if isinstance(root, RootAnalysis):
        root = root.uuid

    return get_system().analysis_tracking.root_analysis_exists(root)


def get_analysis_details(uuid: str) -> Any:
    assert isinstance(uuid, str)

    return get_system().analysis_tracking.get_analysis_details(uuid)


def track_analysis_details(root: RootAnalysis, uuid: str, value: Any) -> bool:
    assert isinstance(root, RootAnalysis)
    assert isinstance(uuid, str)

    # we don't save Analysis that doesn't have the details set
    if value is None:
        return False

    logging.debug(f"tracking {root} analysis details {uuid}")
    exists = analysis_details_exists(root.uuid)
    get_system().analysis_tracking.track_analysis_details(root.uuid, uuid, value)
    if not exists:
        fire_event(EVENT_ANALYSIS_DETAILS_NEW, root, root.uuid)
    else:
        fire_event(EVENT_ANALYSIS_DETAILS_MODIFIED, root, root.uuid)

    return True


def delete_analysis_details(uuid: str) -> bool:
    assert isinstance(uuid, str)

    logging.debug(f"deleting analysis detials {uuid}")
    result = get_system().analysis_tracking.delete_analysis_details(uuid)
    if result:
        fire_event(EVENT_ANALYSIS_DETAILS_DELETED, uuid)

    return result


def analysis_details_exists(uuid: str) -> bool:
    assert isinstance(uuid, str)
    return get_system().analysis_tracking.analysis_details_exists(uuid)
