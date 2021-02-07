# vim: ts=4:sw=4:et:cc=120

from operator import attrgetter

import pytest

from ace.analysis import RootAnalysis, Analysis
from ace.system.analysis_request import (
    AnalysisRequest,
    clear_tracking_by_analysis_module_type,
    delete_analysis_request,
    get_analysis_request_by_observable,
    get_analysis_request_by_request_id,
    get_analysis_requests_by_root,
    get_expired_analysis_requests,
    link_analysis_requests,
    process_expired_analysis_requests,
    track_analysis_request,
)
from ace.system.analysis_module import (
    AnalysisModuleType,
    register_analysis_module_type,
    UnknownAnalysisModuleTypeError,
    delete_analysis_module_type,
)
from ace.system.analysis_tracking import get_root_analysis
from ace.system.constants import *
from ace.system.exceptions import InvalidWorkQueueError
from ace.system.work_queue import add_work_queue, get_next_analysis_request

amt = AnalysisModuleType(name="test", description="test", version="1.0.0", timeout=30, cache_ttl=600)

TEST_1 = "test_1"
TEST_2 = "test_2"

TEST_OWNER = "test_owner"


@pytest.mark.unit
def test_analysis_request_serialization():
    root = RootAnalysis()
    observable = root.add_observable("test", "1.2.3.4")
    request = observable.create_analysis_request(amt)

    assert request == AnalysisRequest.from_dict(request.to_dict())
    assert request == AnalysisRequest.from_json(request.to_json())

    other = AnalysisRequest.from_dict(request.to_dict())
    assert request.id == other.id
    assert request.observable == other.observable
    assert request.type == other.type
    assert request.status == other.status
    assert request.owner == other.owner
    assert request.original_root == other.original_root
    assert request.modified_root == other.modified_root

    other = AnalysisRequest.from_json(request.to_json())
    assert request.id == other.id
    assert request.observable == other.observable
    assert request.type == other.type
    assert request.status == other.status
    assert request.owner == other.owner
    assert request.original_root == other.original_root
    assert request.modified_root == other.modified_root


@pytest.mark.unit
def test_is_observable_analysis_request():
    root = RootAnalysis()
    observable = root.add_observable("test", "1.2.3.4")
    request = observable.create_analysis_request(amt)
    assert request.is_observable_analysis_request


@pytest.mark.unit
def test_is_observable_analysis_result():
    root = RootAnalysis()
    observable = root.add_observable("test", "1.2.3.4")
    request = observable.create_analysis_request(amt)
    request.initialize_result()
    assert request.is_observable_analysis_result


@pytest.mark.unit
def test_is_root_analysis_request():
    root = RootAnalysis()
    request = root.create_analysis_request()
    assert request.is_root_analysis_request


@pytest.mark.integration
def test_request_observables():
    root = RootAnalysis()
    observable = root.add_observable("test", TEST_1)
    request = observable.create_analysis_request(amt)
    # request.observables should return the observable in the request
    observables = request.observables
    assert len(observables) == 1
    assert observables[0].type == "test"
    assert observables[0].value == TEST_1


@pytest.mark.integration
def test_result_observables():
    amt = register_analysis_module_type(AnalysisModuleType("test", ""))
    root = RootAnalysis()
    observable = root.add_observable("test", TEST_1)
    root.save()
    request = observable.create_analysis_request(amt)
    root = get_root_analysis(root)
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


@pytest.mark.integration
def test_lock_analysis_request():
    root = RootAnalysis()
    request = root.create_analysis_request()
    track_analysis_request(request)
    assert request.lock()
    assert not request.lock()
    assert request.unlock()
    assert not request.unlock()
    assert request.lock()


@pytest.mark.integration
def test_track_analysis_request():
    root = RootAnalysis()
    request = root.create_analysis_request()
    track_analysis_request(request)
    assert get_analysis_request_by_request_id(request.id) == request
    assert get_analysis_requests_by_root(root.uuid) == [request]
    assert delete_analysis_request(request.id)
    assert get_analysis_request_by_request_id(request.id) is None
    assert not get_analysis_requests_by_root(root.uuid)


@pytest.mark.integration
def test_get_analysis_request_by_observable():
    register_analysis_module_type(amt)
    root = RootAnalysis()
    observable = root.add_observable("test", TEST_1)
    request = observable.create_analysis_request(amt)
    track_analysis_request(request)
    assert get_analysis_request_by_observable(observable, amt) == request
    assert delete_analysis_request(request.id)
    assert get_analysis_request_by_observable(observable, amt) is None


@pytest.mark.integration
def test_track_analysis_request_unknown_amt():
    unknown_amt = AnalysisModuleType("other", "")
    root = RootAnalysis()
    observable = root.add_observable("test", TEST_1)
    request = observable.create_analysis_request(unknown_amt)
    with pytest.raises(UnknownAnalysisModuleTypeError):
        track_analysis_request(request)


@pytest.mark.integration
def test_get_expired_analysis_request():
    amt = AnalysisModuleType(name="test", description="test", version="1.0.0", timeout=0, cache_ttl=600)
    register_analysis_module_type(amt)

    root = RootAnalysis()
    observable = root.add_observable("test", TEST_1)
    request = observable.create_analysis_request(amt)
    track_analysis_request(request)
    request.status = TRACKING_STATUS_ANALYZING
    track_analysis_request(request)
    assert get_expired_analysis_requests() == [request]


@pytest.mark.integration
def test_process_expired_analysis_request():
    # set the request to time out immediately
    amt = AnalysisModuleType(name="test", description="test", version="1.0.0", timeout=0, cache_ttl=600)
    register_analysis_module_type(amt)

    root = RootAnalysis()
    observable = root.add_observable("test", TEST_1)
    request = observable.create_analysis_request(amt)
    track_analysis_request(request)
    request.status = TRACKING_STATUS_ANALYZING
    track_analysis_request(request)
    assert get_expired_analysis_requests() == [request]
    add_work_queue(amt.name)
    process_expired_analysis_requests(amt)
    request = get_analysis_request_by_request_id(request.id)
    assert request.status == TRACKING_STATUS_QUEUED
    assert not get_expired_analysis_requests()


@pytest.mark.integration
def test_process_expired_analysis_request_invalid_work_queue():
    # test what happens when we're processing an expired analyiss request for a module type that has been deleted
    amt = AnalysisModuleType(name="test", description="test", version="1.0.0", timeout=0, cache_ttl=600)
    register_analysis_module_type(amt)

    root = RootAnalysis()
    observable = root.add_observable("test", TEST_1)
    request = observable.create_analysis_request(amt)
    track_analysis_request(request)
    request.status = TRACKING_STATUS_ANALYZING
    track_analysis_request(request)
    assert get_expired_analysis_requests() == [request]
    delete_analysis_module_type(amt)
    process_expired_analysis_requests(amt)
    assert get_analysis_request_by_request_id(request.id) is None
    assert not get_expired_analysis_requests()


@pytest.mark.integration
def test_is_cachable():
    amt = AnalysisModuleType(name="test", description="test", version="1.0.0", timeout=0, cache_ttl=600)

    root = RootAnalysis()
    observable = root.add_observable("test", TEST_1)
    assert observable.create_analysis_request(amt).is_cachable
    assert not root.create_analysis_request().is_cachable


@pytest.mark.integration
def test_clear_tracking_by_analysis_module_type():
    amt = AnalysisModuleType("test", "")
    register_analysis_module_type(amt)

    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    request = observable.create_analysis_request(amt)
    track_analysis_request(request)

    assert get_analysis_request_by_request_id(request.id)
    clear_tracking_by_analysis_module_type(amt)
    assert get_analysis_request_by_request_id(request.id) is None


@pytest.mark.unit
def test_link_analysis_requests():
    amt = AnalysisModuleType("test", "")
    register_analysis_module_type(amt)

    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    source_request = observable.create_analysis_request(amt)
    track_analysis_request(source_request)

    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    dest_request = observable.create_analysis_request(amt)
    track_analysis_request(dest_request)

    assert link_analysis_requests(source_request, dest_request)

    # attempting to link against a locked request fails

    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    source_request = observable.create_analysis_request(amt)
    track_analysis_request(source_request)
    assert source_request.lock()

    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    dest_request = observable.create_analysis_request(amt)
    track_analysis_request(dest_request)

    assert not link_analysis_requests(source_request, dest_request)

    # attempting to link against a deleted request fails

    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    source_request = observable.create_analysis_request(amt)
    track_analysis_request(source_request)
    delete_analysis_request(source_request)

    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    dest_request = observable.create_analysis_request(amt)
    track_analysis_request(dest_request)

    assert not link_analysis_requests(source_request, dest_request)
