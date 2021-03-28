# vim: ts=4:sw=4:et:cc=120

from operator import attrgetter

import pytest

from ace.analysis import RootAnalysis, Analysis, AnalysisModuleType
from ace.system.requests import AnalysisRequest
from ace.constants import *
from ace.exceptions import InvalidWorkQueueError, UnknownAnalysisModuleTypeError

amt = AnalysisModuleType(name="test", description="test", version="1.0.0", timeout=30, cache_ttl=600)

TEST_1 = "test_1"
TEST_2 = "test_2"

TEST_OWNER = "test_owner"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_analysis_request_serialization(system):
    root = system.new_root()
    observable = root.add_observable("test", "1.2.3.4")
    request = observable.create_analysis_request(amt)

    assert request == AnalysisRequest.from_dict(request.to_dict(), system)
    assert request == AnalysisRequest.from_json(request.to_json(), system)

    other = AnalysisRequest.from_dict(request.to_dict(), system)
    assert request.id == other.id
    assert request.observable == other.observable
    assert request.type == other.type
    assert request.status == other.status
    assert request.owner == other.owner
    assert request.original_root == other.original_root
    assert request.modified_root == other.modified_root

    other = AnalysisRequest.from_json(request.to_json(), system)
    assert request.id == other.id
    assert request.observable == other.observable
    assert request.type == other.type
    assert request.status == other.status
    assert request.owner == other.owner
    assert request.original_root == other.original_root
    assert request.modified_root == other.modified_root


@pytest.mark.asyncio
@pytest.mark.unit
async def test_is_observable_analysis_request(system):
    root = system.new_root()
    observable = root.add_observable("test", "1.2.3.4")
    request = observable.create_analysis_request(amt)
    assert request.is_observable_analysis_request


@pytest.mark.asyncio
@pytest.mark.unit
async def test_is_observable_analysis_result(system):
    root = system.new_root()
    observable = root.add_observable("test", "1.2.3.4")
    request = observable.create_analysis_request(amt)
    request.initialize_result()
    assert request.is_observable_analysis_result


@pytest.mark.asyncio
@pytest.mark.unit
async def test_is_root_analysis_request(system):
    root = system.new_root()
    request = root.create_analysis_request()
    assert request.is_root_analysis_request


@pytest.mark.asyncio
@pytest.mark.integration
async def test_request_observables(system):
    root = system.new_root()
    observable = root.add_observable("test", TEST_1)
    request = observable.create_analysis_request(amt)
    # request.observables should return the observable in the request
    observables = request.observables
    assert len(observables) == 1
    assert observables[0].type == "test"
    assert observables[0].value == TEST_1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_result_observables(system):
    amt = await system.register_analysis_module_type(AnalysisModuleType("test", ""))
    root = system.new_root()
    observable = root.add_observable("test", TEST_1)
    await root.save()
    request = observable.create_analysis_request(amt)
    root = await system.get_root_analysis(root)
    observable = root.get_observable(observable)
    request.initialize_result()
    analysis = request.modified_observable.add_analysis(type=amt)
    analysis.add_observable("test", TEST_2)
    # request.observables should return the observable in the request as well as any new observables in the analysis
    observables = sorted(request.observables, key=attrgetter("value"))
    assert len(observables) == 2
    assert observables[0].type == "test"
    assert observables[0].value == TEST_1
    assert observables[1].type == "test"
    assert observables[1].value == TEST_2


@pytest.mark.asyncio
@pytest.mark.integration
async def test_lock_analysis_request(system):
    root = system.new_root()
    request = root.create_analysis_request()
    await system.track_analysis_request(request)
    assert await request.lock()
    assert not await request.lock()
    assert await request.unlock()
    assert not await request.unlock()
    assert await request.lock()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_track_analysis_request(system):
    root = system.new_root()
    request = root.create_analysis_request()
    await system.track_analysis_request(request)
    assert await system.get_analysis_request_by_request_id(request.id) == request
    assert await system.get_analysis_requests_by_root(root.uuid) == [request]
    assert await system.delete_analysis_request(request.id)
    assert await system.get_analysis_request_by_request_id(request.id) is None
    assert not await system.get_analysis_requests_by_root(root.uuid)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_analysis_request_by_observable(system):
    await system.register_analysis_module_type(amt)
    root = system.new_root()
    observable = root.add_observable("test", TEST_1)
    request = observable.create_analysis_request(amt)
    await system.track_analysis_request(request)
    assert await system.get_analysis_request_by_observable(observable, amt) == request
    assert await system.delete_analysis_request(request.id)
    assert await system.get_analysis_request_by_observable(observable, amt) is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_track_analysis_request_unknown_amt(system):
    unknown_amt = AnalysisModuleType("other", "")
    root = system.new_root()
    observable = root.add_observable("test", TEST_1)
    request = observable.create_analysis_request(unknown_amt)
    with pytest.raises(UnknownAnalysisModuleTypeError):
        await system.track_analysis_request(request)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_expired_analysis_request(system):
    amt = AnalysisModuleType(name="test", description="test", version="1.0.0", timeout=0, cache_ttl=600)
    await system.register_analysis_module_type(amt)

    root = system.new_root()
    observable = root.add_observable("test", TEST_1)
    request = observable.create_analysis_request(amt)
    await system.track_analysis_request(request)
    request.status = TRACKING_STATUS_ANALYZING
    await system.track_analysis_request(request)
    assert await system.get_expired_analysis_requests() == [request]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_process_expired_analysis_request(system):
    # set the request to time out immediately
    amt = AnalysisModuleType(name="test", description="test", version="1.0.0", timeout=0, cache_ttl=600)
    await system.register_analysis_module_type(amt)

    root = system.new_root()
    observable = root.add_observable("test", TEST_1)
    request = observable.create_analysis_request(amt)
    await system.track_analysis_request(request)
    request.status = TRACKING_STATUS_ANALYZING
    await system.track_analysis_request(request)
    assert await system.get_expired_analysis_requests() == [request]
    await system.add_work_queue(amt.name)
    await system.process_expired_analysis_requests(amt)
    request = await system.get_analysis_request_by_request_id(request.id)
    assert request.status == TRACKING_STATUS_QUEUED
    assert not await system.get_expired_analysis_requests()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_process_expired_analysis_request_invalid_work_queue(system):
    # test what happens when we're processing an expired analyiss request for a module type that has been deleted
    amt = AnalysisModuleType(name="test", description="test", version="1.0.0", timeout=0, cache_ttl=600)
    await system.register_analysis_module_type(amt)

    root = system.new_root()
    observable = root.add_observable("test", TEST_1)
    request = observable.create_analysis_request(amt)
    await system.track_analysis_request(request)
    request.status = TRACKING_STATUS_ANALYZING
    await system.track_analysis_request(request)
    assert await system.get_expired_analysis_requests() == [request]
    await system.delete_analysis_module_type(amt)
    await system.process_expired_analysis_requests(amt)
    assert await system.get_analysis_request_by_request_id(request.id) is None
    assert not await system.get_expired_analysis_requests()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_is_cachable(system):
    amt = AnalysisModuleType(name="test", description="test", version="1.0.0", timeout=0, cache_ttl=600)

    root = system.new_root()
    observable = root.add_observable("test", TEST_1)
    assert observable.create_analysis_request(amt).is_cachable
    assert not root.create_analysis_request().is_cachable


@pytest.mark.asyncio
@pytest.mark.integration
async def test_clear_tracking_by_analysis_module_type(system):
    amt = AnalysisModuleType("test", "")
    await system.register_analysis_module_type(amt)

    root = system.new_root()
    observable = root.add_observable("test", "test")
    request = observable.create_analysis_request(amt)
    await system.track_analysis_request(request)

    assert await system.get_analysis_request_by_request_id(request.id)
    await system.clear_tracking_by_analysis_module_type(amt)
    assert await system.get_analysis_request_by_request_id(request.id) is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_link_analysis_requests(system):
    amt = AnalysisModuleType("test", "")
    await system.register_analysis_module_type(amt)

    root = system.new_root()
    observable = root.add_observable("test", "test")
    source_request = observable.create_analysis_request(amt)
    await system.track_analysis_request(source_request)

    root = system.new_root()
    observable = root.add_observable("test", "test")
    dest_request = observable.create_analysis_request(amt)
    await system.track_analysis_request(dest_request)

    assert await system.link_analysis_requests(source_request, dest_request)

    # attempting to link against a locked request fails

    root = system.new_root()
    observable = root.add_observable("test", "test")
    source_request = observable.create_analysis_request(amt)
    await system.track_analysis_request(source_request)
    assert await source_request.lock()

    root = system.new_root()
    observable = root.add_observable("test", "test")
    dest_request = observable.create_analysis_request(amt)
    await system.track_analysis_request(dest_request)

    assert not await system.link_analysis_requests(source_request, dest_request)

    # attempting to link against a deleted request fails

    root = system.new_root()
    observable = root.add_observable("test", "test")
    source_request = observable.create_analysis_request(amt)
    await system.track_analysis_request(source_request)
    await system.delete_analysis_request(source_request)

    root = system.new_root()
    observable = root.add_observable("test", "test")
    dest_request = observable.create_analysis_request(amt)
    await system.track_analysis_request(dest_request)

    assert not await system.link_analysis_requests(source_request, dest_request)
