# vim: ts=4:sw=4:et:cc=120

import json

from dataclasses import dataclass, field
from typing import Union, Optional

from ace.analysis import Observable, RootAnalysis, AnalysisModuleType
from ace.system import ACESystemInterface, get_system, get_logger
from ace.system.constants import EVENT_AMT_NEW, EVENT_AMT_MODIFIED, EVENT_AMT_DELETED
from ace.system.events import fire_event
from ace.system.exceptions import (
    AnalysisModuleTypeDependencyError,
    CircularDependencyError,
)


class AnalysisModuleTrackingInterface(ACESystemInterface):
    def track_analysis_module_type(self, amt: AnalysisModuleType):
        raise NotImplementedError()

    def delete_analysis_module_type(self, name: str):
        raise NotImplementedError()

    def get_analysis_module_type(self, name: str) -> Union[AnalysisModuleType, None]:
        raise NotImplementedError()

    def get_all_analysis_module_types(self) -> list[AnalysisModuleType]:
        raise NotImplementedError()


def _circ_dep_check(
    source_amt: AnalysisModuleType,
    target_amt: Optional[AnalysisModuleType] = None,
    chain: list[AnalysisModuleType] = [],
):
    chain = chain[:]

    if target_amt is None:
        target_amt = source_amt

    chain.append(target_amt)

    for dep in target_amt.dependencies:
        if source_amt.name == dep:
            raise CircularDependencyError(" -> ".join([_.name for _ in chain]))

        _circ_dep_check(source_amt, get_analysis_module_type(dep), chain)


def register_analysis_module_type(amt: AnalysisModuleType) -> AnalysisModuleType:
    """Registers the given AnalysisModuleType with the system."""
    from ace.system.work_queue import add_work_queue

    # make sure all the dependencies exist
    for dep in amt.dependencies:
        if get_analysis_module_type(dep) is None:
            raise AnalysisModuleTypeDependencyError(f"unknown type {dep}")

    # make sure there are no circular (or self) dependencies
    _circ_dep_check(amt)

    current_type = get_analysis_module_type(amt.name)
    if current_type is None:
        add_work_queue(amt.name)

    # regardless we take this to be the new registration for this analysis module
    # any updates to version or cache keys would be saved here
    track_analysis_module_type(amt)

    if current_type and not current_type.version_matches(amt):
        fire_event(EVENT_AMT_MODIFIED, amt)
    elif current_type is None:
        fire_event(EVENT_AMT_NEW, amt)

    return amt


def track_analysis_module_type(amt: AnalysisModuleType):
    assert isinstance(amt, AnalysisModuleType)
    get_logger().debug(f"tracking analysis module type {amt}")
    return get_system().module_tracking.track_analysis_module_type(amt)


def get_analysis_module_type(name: str) -> Union[AnalysisModuleType, None]:
    """Returns the registered AnalysisModuleType by name, or None if it has not been or is no longer registered."""
    assert isinstance(name, str)
    return get_system().module_tracking.get_analysis_module_type(name)


def delete_analysis_module_type(amt: Union[AnalysisModuleType, str]) -> bool:
    """Deletes (unregisters) the given AnalysisModuleType from the system.
    Any outstanding requests for this type are discarded.
    Returns True if the analysis module type was deleted, False otherwise.
    If the type does not exist then False is returned."""
    from ace.system.analysis_request import clear_tracking_by_analysis_module_type
    from ace.system.work_queue import delete_work_queue
    from ace.system.caching import delete_cached_analysis_results_by_module_type

    if isinstance(amt, str):
        amt = get_analysis_module_type(amt)

    if not get_analysis_module_type(amt.name):
        return False

    get_logger().info(f"deleting analysis module type {amt}")

    # remove the work queue for the module
    delete_work_queue(amt.name)
    # remove the module
    get_system().module_tracking.delete_analysis_module_type(amt)
    # remove any outstanding requests from tracking
    clear_tracking_by_analysis_module_type(amt)
    # remove any cached analysis results for this type
    delete_cached_analysis_results_by_module_type(amt)

    fire_event(EVENT_AMT_DELETED, amt)
    return True


def get_all_analysis_module_types() -> list[AnalysisModuleType]:
    """Returns the full list of all registered analysis module types."""
    return get_system().module_tracking.get_all_analysis_module_types()
