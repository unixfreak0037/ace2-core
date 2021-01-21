# vim: ts=4:sw=4:et:cc=120

import logging
from typing import Union, Optional

from ace.system import ACESystemInterface, get_system
from ace.system.constants import TRACKING_STATUS_ANALYZING
from ace.system.analysis_module import (
    AnalysisModuleType,
    AnalysisModuleTypeVersionError,
    track_analysis_module_type,
    get_analysis_module_type,
)
from ace.system.analysis_request import (
    AnalysisRequest,
    process_expired_analysis_requests,
    track_analysis_request,
    get_analysis_request_by_request_id,
)
from ace.system.locking import LockAcquireFailed


class WorkQueueManagerInterface(ACESystemInterface):
    def delete_work_queue(self, name: str) -> bool:
        """Deletes an existing work queue.
        A deleted work queue is removed from the system, and all work items in the queue are also deleted."""
        raise NotImplementedError()

    def add_work_queue(self, name: str):
        """Creates a new work queue for the given analysis module type."""
        raise NotImplementedError()

    def put_work(self, amt: str, analysis_request: AnalysisRequest):
        """Adds the AnalysisRequest to the end of the work queue for the given type."""
        raise NotImplementedError()

    def get_work(self, amt: str, timeout: int) -> Union[AnalysisRequest, None]:
        """Gets the next AnalysisRequest from the work queue for the given type, or None if no content is available.

        Args:
            timeout: how long to wait in seconds
            Passing 0 returns immediately

        """
        raise NotImplementedError()

    def get_queue_size(self, amt: str) -> int:
        """Returns the current size of the work queue for the given type."""
        raise NotImplementedError()


def get_work(amt: Union[AnalysisModuleType, str], timeout: int) -> Union[AnalysisRequest, None]:
    assert isinstance(amt, AnalysisModuleType) or isinstance(amt, str)
    assert isinstance(timeout, int)

    if isinstance(amt, AnalysisModuleType):
        amt = amt.name

    return get_system().work_queue.get_work(amt, timeout)


def put_work(amt: Union[AnalysisModuleType, str], analysis_request: AnalysisRequest):
    assert isinstance(amt, AnalysisModuleType) or isinstance(amt, str)
    assert isinstance(analysis_request, AnalysisRequest)

    if isinstance(amt, AnalysisModuleType):
        amt = amt.name

    logging.debug(f"adding request {analysis_request} to work queue for {amt}")
    return get_system().work_queue.put_work(amt, analysis_request)


def get_queue_size(amt: Union[AnalysisModuleType, str]) -> int:
    assert isinstance(amt, AnalysisModuleType) or isinstance(amt, str)

    if isinstance(amt, AnalysisModuleType):
        amt = amt.name

    return get_system().work_queue.get_queue_size(amt)


def delete_work_queue(amt: Union[AnalysisModuleType, str]) -> bool:
    assert isinstance(amt, AnalysisModuleType) or isinstance(amt, str)

    if isinstance(amt, AnalysisModuleType):
        amt = amt.name

    logging.debug(f"deleting work queue for {amt}")
    return get_system().work_queue.delete_work_queue(amt)


def add_work_queue(amt: Union[AnalysisModuleType, str]):
    assert isinstance(amt, AnalysisModuleType) or isinstance(amt, str)
    if isinstance(amt, AnalysisModuleType):
        amt = amt.name

    logging.debug(f"adding work queue for {amt}")
    get_system().work_queue.add_work_queue(amt)


def get_next_analysis_request(
    owner_uuid: str, amt: Union[AnalysisModuleType, str], timeout: Optional[int] = 0
) -> Union[AnalysisRequest, None]:
    """Returns the next AnalysisRequest for the given AnalysisModuleType, or None if nothing is available.
    This function is called by the analysis modules to get the next work item.

    Args:
        owner_uuid: Represents the owner of the request.
        amt: The AnalysisModuleType that the request is for.
        timeout: How long to wait (in seconds) for a work request to come in.
            Defaults to 0 seconds which immediately returns a result.

    Returns:
        An AnalysisRequest to be processed, or None if no work requests are available."""

    assert isinstance(owner_uuid, str) and owner_uuid
    assert isinstance(amt, AnalysisModuleType) or isinstance(amt, str)
    assert isinstance(timeout, int)

    # make sure expired analysis requests go back in the work queues
    process_expired_analysis_requests()

    # make sure that the requested analysis module hasn't been replaced by a newer version
    # if that's the case then the request fails and the requestor needs to update to the new version
    existing_amt = get_analysis_module_type(amt.name)
    if existing_amt and not existing_amt.version_matches(amt):
        logging.info(f"requested amt {amt} version mismatch against {existing_amt}")
        raise AnalysisModuleTypeVersionError(amt, existing_amt)

    while True:
        next_ar = get_work(amt, timeout)

        if next_ar:
            # TODO how long do we wait for this?
            # so there's an assumption here that this AnalysisRequest will not be grabbed by another process
            try:
                with next_ar.lock():
                    # get the most recent copy of the analysis request
                    next_ar = get_analysis_request_by_request_id(next_ar.id)
                    # if it was deleted then we ignore it and move on to the next one
                    # this can happen if the request is deleted while it's waiting in the queue
                    if not next_ar:
                        continue

                    # set the owner, status then update
                    next_ar.owner = owner_uuid
                    next_ar.status = TRACKING_STATUS_ANALYZING
                    logging.debug(f"assigned analysis request {next_ar} to {owner_uuid}")
                    track_analysis_request(next_ar)

            except LockAcquireFailed as e:
                # if we are unable to get the lock on the request then put it back into the queue
                put_work(amt, next_ar)
                raise e

        return next_ar
