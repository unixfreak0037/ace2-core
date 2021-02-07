# vim: ts=4:sw=4:et:cc=120

import uuid

import pytest

from ace.analysis import RootAnalysis
from ace.system.analysis_module import AnalysisModuleType, UnknownAnalysisModuleTypeError, register_analysis_module_type
from ace.system.analysis_request import (
    AnalysisRequest,
    delete_analysis_request,
    get_analysis_request_by_request_id,
    process_expired_analysis_requests,
    submit_analysis_request,
    track_analysis_request,
)
from ace.system.constants import *
from ace.system.work_queue import (
    add_work_queue,
    delete_work_queue,
    get_next_analysis_request,
    get_queue_size,
)

amt_1 = AnalysisModuleType(name="test", description="test", version="1.0.0", timeout=30, cache_ttl=600)

amt_2 = AnalysisModuleType(name="test", description="test", version="1.0.0", timeout=30, cache_ttl=600)

TEST_1 = "test_1"
TEST_OWNER = str(uuid.uuid4())


@pytest.mark.integration
def test_add_work_queue():
    add_work_queue(amt_1)
    assert get_queue_size(amt_1) == 0

    # add an existing work queue
    add_work_queue(amt_1)
    assert get_queue_size(amt_1) == 0


@pytest.mark.integration
def test_delete_work_queue():
    add_work_queue(amt_1)
    assert delete_work_queue(amt_1.name)
    with pytest.raises(UnknownAnalysisModuleTypeError):
        get_queue_size(amt_1)


@pytest.mark.integration
def test_reference_invalid_work_queue():
    with pytest.raises(UnknownAnalysisModuleTypeError):
        get_queue_size(amt_1)


@pytest.mark.integration
def test_get_next_analysis_request():
    register_analysis_module_type(amt_1)
    root = RootAnalysis()
    observable = root.add_observable("test", TEST_1)
    request = AnalysisRequest(root, observable, amt_1)
    submit_analysis_request(request)

    next_ar = get_next_analysis_request(TEST_OWNER, amt_1, 0)
    assert next_ar == request
    assert next_ar.status == TRACKING_STATUS_ANALYZING
    assert next_ar.owner == TEST_OWNER
    assert get_next_analysis_request(TEST_OWNER, amt_1, 0) is None


@pytest.mark.integration
def test_get_next_analysis_request_expired():

    amt = AnalysisModuleType(
        name="test", description="test", version="1.0.0", timeout=0, cache_ttl=600  # immediately expire
    )

    register_analysis_module_type(amt)
    root = RootAnalysis()
    observable = root.add_observable("test", TEST_1)
    request = AnalysisRequest(root, observable, amt)
    submit_analysis_request(request)

    next_ar = get_next_analysis_request(TEST_OWNER, amt, 0)
    assert next_ar == request
    assert next_ar.status == TRACKING_STATUS_ANALYZING
    assert next_ar.owner == TEST_OWNER

    # this next call should trigger the move of the expired analysis request
    # and since it expires right away we should see the same request again
    next_ar = get_next_analysis_request(TEST_OWNER, amt, 0)
    assert next_ar == request

    # execute this manually
    process_expired_analysis_requests(amt)

    # should be back in the queue
    request = get_analysis_request_by_request_id(request.id)
    assert request.status == TRACKING_STATUS_QUEUED
    assert request.owner is None

    # and then we should get it again
    next_ar = get_next_analysis_request(TEST_OWNER, amt, 0)
    assert next_ar == request


@pytest.mark.integration
def test_get_next_analysis_request_deleted():
    amt = AnalysisModuleType("test", "")
    register_analysis_module_type(amt)
    root = RootAnalysis()
    observable = root.add_observable("test", TEST_1)
    request = AnalysisRequest(root, observable, amt)
    submit_analysis_request(request)
    delete_analysis_request(request)
    assert get_analysis_request_by_request_id(request.id) is None

    # should be nothing there to get since the request was deleted
    assert get_next_analysis_request("owner", amt, 0) is None
