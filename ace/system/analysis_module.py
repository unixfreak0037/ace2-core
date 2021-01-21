# vim: ts=4:sw=4:et:cc=120

import json
import logging

from dataclasses import dataclass, field
from typing import Union, Optional

from ace.analysis import Observable, RootAnalysis, AnalysisModuleType
from ace.system import ACESystemInterface, get_system


class UnknownAnalysisModuleTypeError(Exception):
    """Raised when a request is made for an unknown (unregistered analysis module type.)"""

    def __init__(self, amt: Union[AnalysisModuleType, str]):
        super().__init__(f"unknown AnalysisModuleType {amt}")


class CircularDependencyError(Exception):
    """Raised when there is an attempt to register a type that would cause a circular dependency."""

    def __init__(self, chain: list[AnalysisModuleType]):
        super().__init__("circular dependency error: {}".format(" -> ".join([_.name for _ in chain])))


class AnalysisModuleTypeVersionError(Exception):
    """Raised when a request for a analysis with an out-of-date version is made."""

    pass


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
            raise CircularDependencyError(chain)

        _circ_dep_check(source_amt, get_analysis_module_type(dep), chain)


def register_analysis_module_type(amt: AnalysisModuleType) -> AnalysisModuleType:
    """Registers the given AnalysisModuleType with the system."""

    # make sure all the dependencies exist
    for dep in amt.dependencies:
        if get_analysis_module_type(dep) is None:
            logging.error(f"registration for {amt} failed: dependency on unknown type {dep}")
            raise UnknownAnalysisModuleTypeError(amt)

    # make sure there are no circular (or self) dependencies
    _circ_dep_check(amt)

    current_type = get_analysis_module_type(amt.name)
    if current_type is None:
        get_system().work_queue.add_work_queue(amt.name)

    # regardless we take this to be the new registration for this analysis module
    # any updates to version or cache keys would be saved here
    track_analysis_module_type(amt)
    return amt


def track_analysis_module_type(amt: AnalysisModuleType):
    assert isinstance(amt, AnalysisModuleType)
    logging.debug(f"tracking analysis module type {amt}")
    return get_system().module_tracking.track_analysis_module_type(amt)


def get_analysis_module_type(name: str) -> Union[AnalysisModuleType, None]:
    """Returns the registered AnalysisModuleType by name, or None if it has not been or is no longer registered."""
    assert isinstance(name, str)
    return get_system().module_tracking.get_analysis_module_type(name)


def delete_analysis_module_type(amt: Union[AnalysisModuleType, str]):
    """Deletes (unregisters) the given AnalysisModuleType from the system.
    Any outstanding requests for this type are discarded."""
    from ace.system.analysis_request import clear_tracking_by_analysis_module_type
    from ace.system.work_queue import delete_work_queue
    from ace.system.caching import delete_cached_analysis_results_by_module_type

    if isinstance(amt, str):
        amt = get_analysis_module_type(amt)

    logging.info(f"deleting analysis module type {amt}")

    # remove the work queue for the module
    delete_work_queue(amt.name)
    # remove the module
    get_system().module_tracking.delete_analysis_module_type(amt)
    # remove any outstanding requests from tracking
    clear_tracking_by_analysis_module_type(amt)
    # remove any cached analysis results for this type
    delete_cached_analysis_results_by_module_type(amt)


def get_all_analysis_module_types() -> list[AnalysisModuleType]:
    """Returns the full list of all registered analysis module types."""
    return get_system().module_tracking.get_all_analysis_module_types()
