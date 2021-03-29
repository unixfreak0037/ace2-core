# vim: ts=4:sw=4:et:cc=120

import uuid

import pytest

from ace.analysis import RootAnalysis, AnalysisModuleType
from ace.system.requests import AnalysisRequest
from ace.constants import *
from ace.exceptions import UnknownAnalysisModuleTypeError

amt_1 = AnalysisModuleType(name="test", description="test", version="1.0.0", timeout=30, cache_ttl=600)

amt_2 = AnalysisModuleType(name="test", description="test", version="1.0.0", timeout=30, cache_ttl=600)

TEST_1 = "test_1"
TEST_OWNER = str(uuid.uuid4())


@pytest.mark.asyncio
@pytest.mark.integration
async def test_add_work_queue(system):
    await system.add_work_queue(amt_1)
    assert await system.get_queue_size(amt_1) == 0

    # add an existing work queue
    await system.add_work_queue(amt_1)
    assert await system.get_queue_size(amt_1) == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_work_queue(system):
    await system.add_work_queue(amt_1)
    assert await system.delete_work_queue(amt_1.name)
    with pytest.raises(UnknownAnalysisModuleTypeError):
        await system.get_queue_size(amt_1)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_reference_invalid_work_queue(system):
    with pytest.raises(UnknownAnalysisModuleTypeError):
        await system.get_queue_size(amt_1)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_next_analysis_request(system):
    await system.register_analysis_module_type(amt_1)
    root = system.new_root()
    observable = root.add_observable("test", TEST_1)
    request = AnalysisRequest(system, root, observable, amt_1)
    await system.submit_analysis_request(request)

    next_ar = await system.get_next_analysis_request(TEST_OWNER, amt_1, 0)
    assert next_ar == request
    assert next_ar.status == TRACKING_STATUS_ANALYZING
    assert next_ar.owner == TEST_OWNER
    assert await system.get_next_analysis_request(TEST_OWNER, amt_1, 0) is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_next_analysis_request_by_name(system):
    await system.register_analysis_module_type(amt_1)
    root = system.new_root()
    observable = root.add_observable("test", TEST_1)
    request = AnalysisRequest(system, root, observable, amt_1)
    await system.submit_analysis_request(request)

    next_ar = await system.get_next_analysis_request(TEST_OWNER, "test", 0, version="1.0.0")
    assert next_ar == request
    assert next_ar.status == TRACKING_STATUS_ANALYZING
    assert next_ar.owner == TEST_OWNER
    assert await system.get_next_analysis_request(TEST_OWNER, "test", 0, version="1.0.0") is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_next_analysis_request_expired(system):

    amt = AnalysisModuleType(
        name="test", description="test", version="1.0.0", timeout=0, cache_ttl=600  # immediately expire
    )

    await system.register_analysis_module_type(amt)
    root = system.new_root()
    observable = root.add_observable("test", TEST_1)
    request = AnalysisRequest(system, root, observable, amt)
    await system.submit_analysis_request(request)

    next_ar = await system.get_next_analysis_request(TEST_OWNER, amt, 0)
    assert next_ar == request
    assert next_ar.status == TRACKING_STATUS_ANALYZING
    assert next_ar.owner == TEST_OWNER

    # this next call should trigger the move of the expired analysis request
    # and since it expires right away we should see the same request again
    next_ar = await system.get_next_analysis_request(TEST_OWNER, amt, 0)
    assert next_ar == request

    # execute this manually
    await system.process_expired_analysis_requests(amt)

    # should be back in the queue
    request = await system.get_analysis_request_by_request_id(request.id)
    assert request.status == TRACKING_STATUS_QUEUED
    assert request.owner is None

    # and then we should get it again
    next_ar = await system.get_next_analysis_request(TEST_OWNER, amt, 0)
    assert next_ar == request


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_next_analysis_request_deleted(system):
    amt = AnalysisModuleType("test", "")
    await system.register_analysis_module_type(amt)
    root = system.new_root()
    observable = root.add_observable("test", TEST_1)
    request = AnalysisRequest(system, root, observable, amt)
    await system.submit_analysis_request(request)
    await system.delete_analysis_request(request)
    assert await system.get_analysis_request_by_request_id(request.id) is None

    # should be nothing there to get since the request was deleted
    assert await system.get_next_analysis_request("owner", amt, 0) is None
