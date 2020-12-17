# vim: ts=4:sw=4:et:cc=120

import uuid

import pytest

from ace.analysis import RootAnalysis
from ace.constants import *
from ace.system.analysis_module import AnalysisModuleType
from ace.system.analysis_request import (
    AnalysisRequest,
    get_analysis_request_by_request_id,
    process_expired_analysis_requests,
    submit_analysis_request,
    track_analysis_request,
)
from ace.system.constants import *
from ace.system.work_queue import (
    WorkQueue,
    get_next_analysis_request,
    get_work_queue,
    invalidate_work_queue,
    register_work_queue,
)

amt_1 = AnalysisModuleType(name="test", description="test", version="1.0.0", timeout=30, cache_ttl=600)

amt_2 = AnalysisModuleType(name="test", description="test", version="1.0.0", timeout=30, cache_ttl=600)

TEST_1 = "test_1"
TEST_OWNER = str(uuid.uuid4())


@pytest.mark.integration
def test_register_work_queue():
    wq = register_work_queue(amt_1)
    assert get_work_queue(amt_1) is wq


@pytest.mark.integration
def test_register_existing_work_queue():
    wq_1 = register_work_queue(amt_1)
    assert get_work_queue(amt_1) is wq_1

    # should still have the same work queue
    wq_2 = register_work_queue(amt_2)
    assert get_work_queue(amt_2) is wq_1


@pytest.mark.integration
def test_invalidate_work_queue():
    wq_1 = register_work_queue(amt_1)
    assert get_work_queue(amt_1) is wq_1
    assert invalidate_work_queue(amt_1.name)
    assert get_work_queue(amt_1) is None


@pytest.mark.integration
def test_get_invalid_work_queue():
    assert get_work_queue(amt_1) is None


@pytest.mark.integration
def test_get_next_analysis_request():
    register_work_queue(amt_1)
    root = RootAnalysis()
    observable = root.add_observable(F_TEST, TEST_1)
    request = AnalysisRequest(root, observable, amt_1)
    submit_analysis_request(request)

    next_ar = get_next_analysis_request(TEST_OWNER, amt_1, None)
    assert next_ar == request
    assert next_ar.status == TRACKING_STATUS_ANALYZING
    assert next_ar.owner == TEST_OWNER
    assert get_next_analysis_request(TEST_OWNER, amt_1, 0) is None


@pytest.mark.integration
def test_get_next_analysis_request_expired():

    amt = AnalysisModuleType(
        name="test", description="test", version="1.0.0", timeout=0, cache_ttl=600  # immediately expire
    )

    register_work_queue(amt)
    root = RootAnalysis()
    observable = root.add_observable(F_TEST, TEST_1)
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
    process_expired_analysis_requests()

    # should be back in the queue
    request = get_analysis_request_by_request_id(request.id)
    assert request.status == TRACKING_STATUS_QUEUED
    assert request.owner is None

    # and then we should get it again
    next_ar = get_next_analysis_request(TEST_OWNER, amt, 0)
    assert next_ar == request
