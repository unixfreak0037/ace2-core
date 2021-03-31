# vim: ts=4:sw=4:et:cc=120
#
# full ACE system testing
#

import logging

import uuid
import threading

from ace.analysis import AnalysisModuleType, RootAnalysis, Analysis, Observable
from ace.system.requests import AnalysisRequest
from ace.constants import *
from ace.exceptions import (
    AnalysisModuleTypeExtendedVersionError,
    AnalysisModuleTypeVersionError,
    ExpiredAnalysisRequestError,
    UnknownAnalysisModuleTypeError,
    UnknownAnalysisRequestError,
)

import pytest


@pytest.mark.asyncio
@pytest.mark.system
async def test_basic_analysis(system):

    # define an owner
    owner_uuid = str(uuid.uuid4())

    # register a basic analysis module
    amt = AnalysisModuleType("test", "", ["test"])
    assert await system.register_analysis_module_type(amt)

    # submit an analysis request with a single observable
    root = system.new_root()
    observable = root.add_observable("test", "test")
    await system.process_analysis_request(root.create_analysis_request())

    # have the amt receive the next work item
    request = await system.get_next_analysis_request(owner_uuid, amt, 0)
    assert isinstance(request, AnalysisRequest)

    analysis_details = {"test": "result"}

    # "analyze" it
    request.initialize_result()
    request.modified_observable.add_analysis(type=amt, details=analysis_details)

    # submit the result of the analysis
    await system.process_analysis_request(request)

    # check the results
    root = await system.get_root_analysis(root.uuid)
    assert isinstance(root, RootAnalysis)
    observable = root.get_observable(observable)
    assert isinstance(observable, Observable)
    analysis = observable.get_analysis(amt)
    assert isinstance(analysis, Analysis)
    assert await analysis.get_details() == analysis_details


@pytest.mark.asyncio
@pytest.mark.system
async def test_multiple_amts(system):
    """Test having two different AMTs for the same observable type."""

    # define two owners
    owner_1 = str(uuid.uuid4())
    owner_2 = str(uuid.uuid4())

    # register two basic analysis modules
    amt_1 = AnalysisModuleType("test_1", "", ["test"])
    assert await system.register_analysis_module_type(amt_1)

    amt_2 = AnalysisModuleType("test_2", "", ["test"])
    assert await system.register_analysis_module_type(amt_2)

    # submit an analysis request with a single observable
    root = system.new_root()
    observable = root.add_observable("test", "test")
    await system.process_analysis_request(root.create_analysis_request())

    # have both amts receive work items
    request_1 = await system.get_next_analysis_request(owner_1, amt_1, 0)
    assert isinstance(request_1, AnalysisRequest)

    request_2 = await system.get_next_analysis_request(owner_2, amt_2, 0)
    assert isinstance(request_2, AnalysisRequest)

    analysis_details_1 = {"test_1": "result_1"}
    analysis_details_2 = {"test_2": "result_2"}

    # "analyze" them
    request_1.initialize_result()
    request_1.modified_observable.add_analysis(type=amt_1, details=analysis_details_1)

    # submit the result of the analysis
    await system.process_analysis_request(request_1)

    request_2.initialize_result()
    request_2.modified_observable.add_analysis(type=amt_2, details=analysis_details_2)

    # submit the result of the analysis
    await system.process_analysis_request(request_2)

    # check the results
    root = await system.get_root_analysis(root.uuid)
    assert isinstance(root, RootAnalysis)
    observable = root.get_observable(observable)
    assert isinstance(observable, Observable)
    analysis = observable.get_analysis(amt_1)
    assert isinstance(analysis, Analysis)
    assert await analysis.get_details() == analysis_details_1
    analysis = observable.get_analysis(amt_2)
    assert isinstance(analysis, Analysis)
    assert await analysis.get_details() == analysis_details_2


@pytest.mark.asyncio
@pytest.mark.system
async def test_multiple_amt_workers(system):
    """Test having more than one worker for a single amt."""

    # define two owners
    owner_uuid_1 = str(uuid.uuid4())
    owner_uuid_2 = str(uuid.uuid4())

    # register a single basic analysis module
    amt = AnalysisModuleType("test", "", ["test"])
    assert await system.register_analysis_module_type(amt)

    # submit an analysis request with a single observable
    root = system.new_root()
    observable = root.add_observable("test", "test")
    await system.process_analysis_request(root.create_analysis_request())

    # have both workers try to grab the request
    request_1 = await system.get_next_analysis_request(owner_uuid_1, amt, 0)
    request_2 = await system.get_next_analysis_request(owner_uuid_2, amt, 0)

    # one of them should have received it
    assert (request_1 is not None and request_2 is None) or (request_1 is None and request_2 is not None)


@pytest.mark.asyncio
@pytest.mark.system
async def test_expected_status(system):
    """Test that the status of various components is what we expect as we step through the process."""

    # define an owner
    owner_uuid = str(uuid.uuid4())

    # register a basic analysis module
    amt = AnalysisModuleType("test", "", ["test"])
    assert await system.register_analysis_module_type(amt)

    # create a new root analysis object
    root = system.new_root()
    observable = root.add_observable("test", "test")

    # this should not be tracked yet
    assert await system.get_root_analysis(root.uuid) is None

    # submit it
    await system.process_analysis_request(root.create_analysis_request())

    # it should be tracked now
    root = await system.get_root_analysis(root.uuid)
    assert isinstance(root, RootAnalysis)

    # and there should be an outstanding analysis request
    observable = root.get_observable(observable)
    assert observable.request_tracking
    request_id = observable.get_analysis_request_id(amt)
    assert request_id
    request = await system.get_analysis_request(request_id)

    assert request.owner is None
    assert request.status == TRACKING_STATUS_QUEUED
    assert not request.result

    # have the amt receive the next work item
    request = await system.get_next_analysis_request(owner_uuid, amt, 0)
    assert isinstance(request, AnalysisRequest)

    # status of the request should have changed
    request = await system.get_analysis_request(request_id)

    assert request.owner == owner_uuid
    assert request.status == TRACKING_STATUS_ANALYZING
    assert not request.result

    analysis_details = {"test": "result"}

    # "analyze" it
    request.initialize_result()
    request.modified_observable.add_analysis(type=amt, details=analysis_details)

    # submit the result of the analysis
    await system.process_analysis_request(request)

    # now this request should not be tracked anymore
    assert await system.get_analysis_request(request_id) is None


@pytest.mark.asyncio
@pytest.mark.system
async def test_amt_version_upgrade(system):
    # register an analysis module for a specific version of the "intel"
    amt = await system.register_analysis_module_type(AnalysisModuleType("test", "", extended_version=["intel:v1"]))

    # (assume amt goes offline)
    # add something to be analyzed
    root = system.new_root()
    observable = root.add_observable("test", "test")
    await root.submit()

    # amt comes back on, re-register
    amt = await system.register_analysis_module_type(AnalysisModuleType("test", "", extended_version=["intel:v1"]))
    request = await system.get_next_analysis_request("test", amt, 0)
    request.initialize_result()
    request.modified_observable.add_analysis(type=amt).add_observable("test", "other")
    await system.process_analysis_request(request)

    # amt gets upgraded from another process
    amt_upgraded = await system.register_analysis_module_type(
        AnalysisModuleType("test", "", extended_version=["intel:v2"])
    )

    # but we're still using the old one so this should fail
    with pytest.raises(AnalysisModuleTypeExtendedVersionError):
        request = await system.get_next_analysis_request("test", amt, 0)

    # and the work queue should still have one entry
    assert await system.get_queue_size(amt_upgraded) == 1


@pytest.mark.asyncio
@pytest.mark.system
async def test_delete_analysis_module_type_outstanding_requests(system):
    amt = await system.register_analysis_module_type(AnalysisModuleType("test", ""))

    root = system.new_root()
    observable = root.add_observable("test", "test")
    await root.submit()

    # should have one request outstanding
    assert await system.get_queue_size(amt) == 1

    await system.delete_analysis_module_type(amt)

    # this should fail because the queue has been delete
    with pytest.raises(UnknownAnalysisModuleTypeError):
        await system.get_next_analysis_request("owner", amt, 0)


@pytest.mark.asyncio
@pytest.mark.system
async def test_delete_analysis_module_type_while_processing_request(system):
    amt = await system.register_analysis_module_type(AnalysisModuleType("test", ""))

    root = system.new_root()
    observable = root.add_observable("test", "test")
    await root.submit()

    # go get the request for processing
    request = await system.get_next_analysis_request("owner", amt, 0)

    # delete the amt while we're processing the request
    await system.delete_analysis_module_type(amt)

    request.initialize_result()
    request.modified_observable.add_analysis(Analysis(type=amt, details={"test": "test"}))

    # should fail since the amt has been removed
    with pytest.raises(UnknownAnalysisRequestError):
        await request.submit()

    # and the request should already be deleted as well
    assert await system.get_analysis_request_by_request_id(request.id) is None


@pytest.mark.asyncio
@pytest.mark.system
async def test_delete_analysis_module_type_linked_results(system):
    amt = AnalysisModuleType("test", "", cache_ttl=300)
    await system.register_analysis_module_type(amt)

    original_root = system.new_root()
    test_observable = original_root.add_observable("test", "test")

    original_request = original_root.create_analysis_request()
    await system.process_analysis_request(original_request)

    # we should have a single work entry in the work queue
    assert await system.get_queue_size(amt) == 1

    # make another request for the same observable but from a different root analysis
    root = system.new_root()
    test_observable = root.add_observable("test", "test")
    root_request = root.create_analysis_request()
    await system.process_analysis_request(root_request)

    # there should still only be one outbound request
    assert await system.get_queue_size(amt) == 1

    # the first analysis request should now be linked to a new analysis request
    request = await system.get_next_analysis_request("owner", amt, 0)
    linked_requests = await system.get_linked_analysis_requests(request)

    # analysis module type gets deleted
    await system.delete_analysis_module_type(amt)

    # both the original request and the linked request should be gone
    assert await system.get_analysis_request_by_request_id(original_request.id) is None
    assert await system.get_analysis_request_by_request_id(request.id) is None


@pytest.mark.asyncio
@pytest.mark.system
async def test_observable_analysis_request_expired(system):

    # define an owner
    owner_uuid = str(uuid.uuid4())

    # register a basic analysis module
    # these are set to expire immediately
    amt = AnalysisModuleType("test", "", ["test"], timeout=0)
    assert await system.register_analysis_module_type(amt)

    # submit an analysis request with a single observable
    root = system.new_root()
    observable = root.add_observable("test", "test")
    await system.process_analysis_request(root.create_analysis_request())

    # have the amt receive the next work item
    request = await system.get_next_analysis_request(owner_uuid, amt, 0)
    assert isinstance(request, AnalysisRequest)

    # now this has already expired
    # define another owner
    other_owner_uuid = str(uuid.uuid4())
    other_request = await system.get_next_analysis_request(other_owner_uuid, amt, 0)

    # we should have received the same request but the ownership should be different
    assert request.id == other_request.id
    assert request.owner != other_request.owner

    # now the first module analyzes and posts requests *after* it expired
    analysis_details = {"test": "result"}
    request.initialize_result()
    request.modified_observable.add_analysis(type=amt, details=analysis_details)
    with pytest.raises(ExpiredAnalysisRequestError) as e:
        await system.process_analysis_request(request)

    # but the second one can
    analysis_details = {"test": "result"}
    other_request.initialize_result()
    other_request.modified_observable.add_analysis(type=amt, details=analysis_details)
    await system.process_analysis_request(other_request)

    # check the results
    root = await system.get_root_analysis(root.uuid)
    assert isinstance(root, RootAnalysis)
    observable = root.get_observable(observable)
    assert isinstance(observable, Observable)
    analysis = observable.get_analysis(amt)
    assert isinstance(analysis, Analysis)
    assert await analysis.get_details() == analysis_details
