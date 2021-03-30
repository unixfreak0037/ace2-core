# vim: ts=4:sw=4:et:cc=120

import threading

import pytest

from ace.analysis import RootAnalysis, AnalysisModuleType
from ace.data_model import Event, ContentMetadata
from ace.system.requests import AnalysisRequest
from ace.system.caching import generate_cache_key
from ace.constants import (
    EVENT_ALERT,
    EVENT_ALERT_SYSTEM_REGISTERED,
    EVENT_ALERT_SYSTEM_UNREGISTERED,
    EVENT_AMT_DELETED,
    EVENT_AMT_MODIFIED,
    EVENT_AMT_NEW,
    EVENT_ANALYSIS_DETAILS_DELETED,
    EVENT_ANALYSIS_DETAILS_MODIFIED,
    EVENT_ANALYSIS_DETAILS_NEW,
    EVENT_ANALYSIS_ROOT_DELETED,
    EVENT_ANALYSIS_ROOT_EXPIRED,
    EVENT_ANALYSIS_ROOT_MODIFIED,
    EVENT_ANALYSIS_ROOT_NEW,
    EVENT_AR_DELETED,
    EVENT_AR_EXPIRED,
    EVENT_AR_NEW,
    EVENT_PROCESSING_REQUEST_ROOT,
    EVENT_PROCESSING_REQUEST_OBSERVABLE,
    EVENT_PROCESSING_REQUEST_RESULT,
    EVENT_CACHE_NEW,
    EVENT_CACHE_HIT,
    EVENT_CONFIG_SET,
    EVENT_STORAGE_DELETED,
    EVENT_STORAGE_NEW,
    EVENT_WORK_ADD,
    EVENT_WORK_ASSIGNED,
    EVENT_WORK_QUEUE_DELETED,
    EVENT_WORK_QUEUE_NEW,
    EVENT_WORK_REMOVE,
    TRACKING_STATUS_ANALYZING,
)
from ace.system.events import EventHandler


class TestEventHandler(EventHandler):
    __test__ = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.event = None
        self.exception = None
        self.sync = threading.Event()

    def handle_event(self, event: Event):
        self.event = event
        self.sync.set()

    def handle_exception(self, event: Event, exception: Exception):
        self.event = event
        self.exception = exception
        self.sync.set()

    def wait(self):
        self.sync.wait(3)

    def reset(self):
        self.event = None
        self.exception = None
        self.sync = threading.Event()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_EVENT_ANALYSIS_ROOT_NEW(system):
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_ANALYSIS_ROOT_NEW, handler)
    root = system.new_root()
    await system.track_root_analysis(root)

    handler.wait()
    assert handler.event.name == EVENT_ANALYSIS_ROOT_NEW
    assert RootAnalysis.from_dict(handler.event.args, system) == root

    handler = TestEventHandler()
    await system.register_event_handler(EVENT_ANALYSIS_ROOT_NEW, handler)
    # already tracked
    await system.track_root_analysis(root)

    assert handler.event is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_EVENT_ANALYSIS_ROOT_MODIFIED(system):
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_ANALYSIS_ROOT_MODIFIED, handler)
    root = system.new_root()
    await system.track_root_analysis(root)

    assert handler.event is None

    handler = TestEventHandler()
    await system.register_event_handler(EVENT_ANALYSIS_ROOT_MODIFIED, handler)
    # already tracked so should fire as modified
    await system.track_root_analysis(root)

    handler.wait()
    assert handler.event.name == EVENT_ANALYSIS_ROOT_MODIFIED
    assert RootAnalysis.from_dict(handler.event.args, system) == root


@pytest.mark.asyncio
@pytest.mark.integration
async def test_EVENT_ANALYSIS_ROOT_DELETED(system):
    root = system.new_root()
    await system.track_root_analysis(root)
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_ANALYSIS_ROOT_DELETED, handler)
    await system.delete_root_analysis(root)

    handler.wait()
    assert handler.event.name == EVENT_ANALYSIS_ROOT_DELETED
    assert handler.event.args == root.uuid

    # since the root was already deleted this should not fire twice
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_ANALYSIS_ROOT_DELETED, handler)
    await system.delete_root_analysis(root)

    assert handler.event is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_EVENT_ANALYSIS_DETAILS_NEW(system):
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_ANALYSIS_DETAILS_NEW, handler)
    root = system.new_root(details={"test": "test"})
    await system.track_root_analysis(root)
    await system.track_analysis_details(root, root.uuid, await root.get_details())

    handler.wait()
    assert handler.event.name == EVENT_ANALYSIS_DETAILS_NEW
    assert RootAnalysis.from_dict(handler.event.args[0], system) == root
    assert handler.event.args[1] == root.uuid

    handler = TestEventHandler()
    await system.register_event_handler(EVENT_ANALYSIS_DETAILS_NEW, handler)
    # already tracked
    await system.track_analysis_details(root, root.uuid, await root.get_details())

    assert handler.event is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_EVENT_ANALYSIS_DETAILS_MODIFIED(system):
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_ANALYSIS_DETAILS_MODIFIED, handler)
    root = system.new_root(details={"test": "test"})
    await system.track_root_analysis(root)
    await system.track_analysis_details(root, root.uuid, await root.get_details())

    assert handler.event is None

    handler = TestEventHandler()
    await system.register_event_handler(EVENT_ANALYSIS_DETAILS_MODIFIED, handler)
    await system.track_analysis_details(root, root.uuid, await root.get_details())

    handler.wait()
    assert handler.event.name == EVENT_ANALYSIS_DETAILS_MODIFIED
    assert RootAnalysis.from_dict(handler.event.args[0], system) == root
    assert handler.event.args[1] == root.uuid


@pytest.mark.asyncio
@pytest.mark.integration
async def test_EVENT_ANALYSIS_DETAILS_DELETED(system):
    handler = TestEventHandler()
    root = RootAnalysis(details={"test": "test"})
    await system.track_root_analysis(root)
    await system.track_analysis_details(root, root.uuid, await root.get_details())

    await system.register_event_handler(EVENT_ANALYSIS_DETAILS_DELETED, handler)
    await system.delete_analysis_details(root.uuid)

    handler.wait()
    assert handler.event.name == EVENT_ANALYSIS_DETAILS_DELETED
    assert handler.event.args == root.uuid

    handler = TestEventHandler()
    await system.register_event_handler(EVENT_ANALYSIS_DETAILS_DELETED, handler)
    await system.delete_analysis_details(root.uuid)

    assert handler.event is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_ALERT_SYSTEM_REGISTERED(system):
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_ALERT_SYSTEM_REGISTERED, handler)
    await system.register_alert_system("test")

    handler.wait()
    assert handler.event.name == EVENT_ALERT_SYSTEM_REGISTERED
    assert handler.event.args == "test"

    handler = TestEventHandler()
    await system.register_event_handler(EVENT_ALERT_SYSTEM_REGISTERED, handler)
    await system.register_alert_system("test")
    assert handler.event is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_ALERT_SYSTEM_REGISTERED(system):
    await system.register_alert_system("test")
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_ALERT_SYSTEM_UNREGISTERED, handler)

    await system.unregister_alert_system("test")
    handler.wait()
    assert handler.event.name == EVENT_ALERT_SYSTEM_UNREGISTERED
    assert handler.event.args == "test"

    handler = TestEventHandler()
    await system.register_event_handler(EVENT_ALERT_SYSTEM_UNREGISTERED, handler)
    await system.unregister_alert_system("test")
    assert handler.event is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_EVENT_ALERT(system):
    await system.register_alert_system("test")
    root = system.new_root()
    await system.track_root_analysis(root)
    root.add_detection_point("test")

    handler = TestEventHandler()
    await system.register_event_handler(EVENT_ALERT, handler)
    await system.submit_alert(root)

    handler.wait()
    assert handler.event.name == EVENT_ALERT
    assert handler.event.args == root.uuid

    # event fires every time
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_ALERT, handler)
    await system.submit_alert(root)

    handler.wait()
    assert handler.event.name == EVENT_ALERT
    assert handler.event.args == root.uuid


@pytest.mark.asyncio
@pytest.mark.integration
async def test_EVENT_AMT_NEW(system):
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_AMT_NEW, handler)

    amt = AnalysisModuleType("test", "")
    await system.register_analysis_module_type(amt)

    handler.wait()
    assert handler.event.name == EVENT_AMT_NEW
    assert AnalysisModuleType.from_dict(handler.event.args) == amt

    handler = TestEventHandler()
    await system.register_event_handler(EVENT_AMT_NEW, handler)

    # already registered so should not be new
    await system.register_analysis_module_type(amt)

    assert handler.event is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_EVENT_AMT_MODIFIED(system):
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_AMT_MODIFIED, handler)

    amt = AnalysisModuleType("test", "")
    await system.register_analysis_module_type(amt)

    assert handler.event is None

    handler = TestEventHandler()
    await system.register_event_handler(EVENT_AMT_MODIFIED, handler)

    # still not modified yet
    await system.register_analysis_module_type(amt)

    assert handler.event is None

    # modify version
    amt.version = "1.0.1"

    handler = TestEventHandler()
    await system.register_event_handler(EVENT_AMT_MODIFIED, handler)

    # modified this time
    await system.register_analysis_module_type(amt)

    handler.wait()
    assert handler.event.name == EVENT_AMT_MODIFIED
    assert AnalysisModuleType.from_dict(handler.event.args) == amt


@pytest.mark.asyncio
@pytest.mark.integration
async def test_EVENT_AMT_DELETED(system):
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_AMT_DELETED, handler)

    amt = AnalysisModuleType("test", "")
    await system.register_analysis_module_type(amt)
    await system.delete_analysis_module_type(amt)

    handler.wait()
    assert handler.event.name == EVENT_AMT_DELETED
    assert AnalysisModuleType.from_dict(handler.event.args) == amt

    handler = TestEventHandler()
    await system.register_event_handler(EVENT_AMT_DELETED, handler)
    await system.delete_analysis_module_type(amt)

    assert handler.event is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_EVENT_AR_NEW(system):
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_AR_NEW, handler)

    root = system.new_root()
    request = root.create_analysis_request()
    await system.track_analysis_request(request)

    handler.wait()
    assert handler.event.name == EVENT_AR_NEW
    assert AnalysisRequest.from_dict(handler.event.args, system) == request

    handler = TestEventHandler()
    await system.register_event_handler(EVENT_AR_NEW, handler)
    await system.track_analysis_request(request)

    # you can re-track a request without harm
    handler.wait()
    assert handler.event.name == EVENT_AR_NEW
    assert AnalysisRequest.from_dict(handler.event.args, system) == request


@pytest.mark.asyncio
@pytest.mark.integration
async def test_EVENT_AR_DELETED(system):
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_AR_DELETED, handler)

    root = system.new_root()
    request = root.create_analysis_request()
    await system.track_analysis_request(request)
    await system.delete_analysis_request(request)

    handler.wait()
    assert handler.event.name == EVENT_AR_DELETED
    assert handler.event.args == request.id

    handler = TestEventHandler()
    await system.register_event_handler(EVENT_AR_DELETED, handler)
    await system.delete_analysis_request(request)
    assert handler.event is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_EVENT_AR_EXPIRED(system):
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_AR_EXPIRED, handler)

    amt = AnalysisModuleType(name="test", description="test", version="1.0.0", timeout=0, cache_ttl=600)
    await system.register_analysis_module_type(amt)

    root = system.new_root()
    observable = root.add_observable("test", "test")
    request = observable.create_analysis_request(amt)
    await system.track_analysis_request(request)
    request.status = TRACKING_STATUS_ANALYZING
    await system.track_analysis_request(request)

    await system.process_expired_analysis_requests(amt)

    handler.wait()
    assert handler.event.name == EVENT_AR_EXPIRED
    assert AnalysisRequest.from_dict(handler.event.args, system) == request


@pytest.mark.asyncio
@pytest.mark.integration
async def test_EVENT_CACHE_NEW(system):
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_CACHE_NEW, handler)

    amt = AnalysisModuleType(name="test", description="", cache_ttl=600)
    root = system.new_root()
    observable = root.add_observable("test", "test")
    request = observable.create_analysis_request(amt)
    request.initialize_result()
    analysis = request.modified_observable.add_analysis(type=amt)

    assert await system.cache_analysis_result(request) is not None

    handler.wait()
    assert handler.event.name == EVENT_CACHE_NEW
    assert handler.event.args[0] == generate_cache_key(observable, amt)
    assert AnalysisRequest.from_dict(handler.event.args[1], system) == request

    # we can potentially see duplicate cache hits
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_CACHE_NEW, handler)
    assert await system.cache_analysis_result(request) is not None
    handler.wait()
    assert handler.event.name == EVENT_CACHE_NEW
    assert handler.event.args[0] == generate_cache_key(observable, amt)
    assert AnalysisRequest.from_dict(handler.event.args[1], system) == request


@pytest.mark.asyncio
@pytest.mark.integration
async def test_EVENT_CONFIG_SET(system):
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_CONFIG_SET, handler)

    await system.set_config("test", "value")
    handler.wait()
    assert handler.event.name == EVENT_CONFIG_SET
    assert handler.event.args[0] == "test"
    assert handler.event.args[1] == "value"

    # duplicate OK
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_CONFIG_SET, handler)
    await system.set_config("test", "value")
    handler.wait()
    assert handler.event.name == EVENT_CONFIG_SET
    assert handler.event.args[0] == "test"
    assert handler.event.args[1] == "value"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_EVENT_STORAGE_NEW(system):
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_STORAGE_NEW, handler)

    meta = ContentMetadata(name="test")
    sha256 = await system.store_content("test", meta)

    handler.wait()
    assert handler.event.name == EVENT_STORAGE_NEW
    assert handler.event.args[0] == sha256
    event_meta = ContentMetadata.parse_obj(handler.event.args[1])
    assert event_meta.name == "test"
    assert event_meta.sha256 == sha256
    assert event_meta.size == 4

    # duplicates are OK
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_STORAGE_NEW, handler)

    meta = ContentMetadata(name="test")
    sha256 = await system.store_content("test", meta)

    handler.wait()
    assert handler.event.name == EVENT_STORAGE_NEW
    assert handler.event.args[0] == sha256
    event_meta = ContentMetadata.parse_obj(handler.event.args[1])
    assert event_meta.name == "test"
    assert event_meta.sha256 == sha256
    assert event_meta.size == 4


@pytest.mark.asyncio
@pytest.mark.integration
async def test_EVENT_STORAGE_DELETED(system):
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_STORAGE_DELETED, handler)
    meta = ContentMetadata(name="test")
    sha256 = await system.store_content("test", meta)
    await system.delete_content(sha256)

    handler.wait()
    assert handler.event.name == EVENT_STORAGE_DELETED
    assert handler.event.args == sha256

    # duplicate does not fire event (already gone)
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_STORAGE_DELETED, handler)
    await system.delete_content(sha256)
    assert handler.event is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_EVENT_WORK_QUEUE_NEW(system):
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_WORK_QUEUE_NEW, handler)

    await system.add_work_queue("test")
    handler.wait()
    assert handler.event.name == EVENT_WORK_QUEUE_NEW
    assert handler.event.args == "test"

    # duplicate should not fire
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_WORK_QUEUE_NEW, handler)

    await system.add_work_queue("test")
    assert handler.event is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_EVENT_WORK_QUEUE_DELETED(system):
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_WORK_QUEUE_DELETED, handler)

    await system.add_work_queue("test")
    await system.delete_work_queue("test")
    handler.wait()
    assert handler.event.name == EVENT_WORK_QUEUE_DELETED
    assert handler.event.args == "test"

    # duplicate should not fire
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_WORK_QUEUE_DELETED, handler)

    await system.delete_work_queue("test")
    assert handler.event is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_EVENT_WORK_ADD(system):
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_WORK_ADD, handler)

    amt = AnalysisModuleType("test", "")
    await system.register_analysis_module_type(amt)
    root = system.new_root()
    observable = root.add_observable("test", "test")
    request = AnalysisRequest(system, root, observable, amt)
    await system.submit_analysis_request(request)

    handler.wait()
    assert handler.event.name == EVENT_WORK_ADD
    assert handler.event.args[0] == amt.name
    assert AnalysisRequest.from_dict(handler.event.args[1], system) == request


@pytest.mark.asyncio
@pytest.mark.integration
async def test_EVENT_WORK_REMOVE(system):
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_WORK_REMOVE, handler)

    amt = AnalysisModuleType("test", "")
    await system.register_analysis_module_type(amt)
    root = system.new_root()
    observable = root.add_observable("test", "test")
    request = AnalysisRequest(system, root, observable, amt)
    await system.submit_analysis_request(request)
    work = await system.get_work(amt, 0)

    handler.wait()
    assert handler.event.name == EVENT_WORK_REMOVE
    assert handler.event.args[0] == amt.name
    assert AnalysisRequest.from_dict(handler.event.args[1], system) == work

    # can't get fired if you ain't got no work
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_WORK_REMOVE, handler)

    work = await system.get_work(amt, 0)

    assert handler.event is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_EVENT_ANALYSIS_ROOT_EXPIRED(system):
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_ANALYSIS_ROOT_EXPIRED, handler)

    root = system.new_root(expires=True)
    await root.submit()

    handler.wait()
    assert handler.event.name == EVENT_ANALYSIS_ROOT_EXPIRED
    event_root = RootAnalysis.from_dict(handler.event.args, system)
    assert event_root.uuid == root.uuid and event_root.version is not None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_EVENT_CACHE_HIT(system):
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_CACHE_HIT, handler)

    amt = AnalysisModuleType("test", "", cache_ttl=60)
    await system.register_analysis_module_type(amt)
    root = system.new_root()
    observable = root.add_observable("test", "test")
    root_request = root.create_analysis_request()
    await system.process_analysis_request(root_request)
    request = await system.get_next_analysis_request("owner", amt, 0)
    request.initialize_result()
    request.modified_observable.add_analysis(type=amt, details={"test": "test"})
    await system.process_analysis_request(request)
    assert handler.event is None

    root = system.new_root()
    observable = root.add_observable("test", "test")
    root_request = root.create_analysis_request()
    await system.process_analysis_request(root_request)

    handler.wait()
    assert handler.event.name == EVENT_CACHE_HIT
    event_root = RootAnalysis.from_dict(handler.event.args[0], system)
    assert event_root.uuid == root.uuid and event_root.version is not None
    assert handler.event.args[1]["type"] == observable.type
    assert handler.event.args[1]["value"] == observable.value
    assert isinstance(AnalysisRequest.from_dict(handler.event.args[2], system), AnalysisRequest)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_EVENT_WORK_ASSIGNED(system):
    handler = TestEventHandler()
    await system.register_event_handler(EVENT_WORK_ASSIGNED, handler)

    amt = AnalysisModuleType("test", "", cache_ttl=60)
    await system.register_analysis_module_type(amt)
    root = system.new_root()
    observable = root.add_observable("test", "test")
    root_request = root.create_analysis_request()
    await system.process_analysis_request(root_request)
    request = await system.get_next_analysis_request("owner", amt, 0)

    handler.wait()
    assert handler.event.name == EVENT_WORK_ASSIGNED
    assert AnalysisRequest.from_dict(handler.event.args, system) == request


@pytest.mark.asyncio
@pytest.mark.integration
async def test_EVENT_PROCESSING(system):
    root_handler = TestEventHandler()
    await system.register_event_handler(EVENT_PROCESSING_REQUEST_ROOT, root_handler)

    observable_request_handler = TestEventHandler()
    await system.register_event_handler(EVENT_PROCESSING_REQUEST_OBSERVABLE, observable_request_handler)

    amt = AnalysisModuleType("test", "", cache_ttl=60)
    await system.register_analysis_module_type(amt)
    root = system.new_root()
    observable = root.add_observable("test", "test")
    root_request = root.create_analysis_request()
    await system.process_analysis_request(root_request)

    root_handler.wait()
    assert root_handler.event.name == EVENT_PROCESSING_REQUEST_ROOT
    assert AnalysisRequest.from_dict(root_handler.event.args, system) == root_request

    request = await system.get_next_analysis_request("owner", amt, 0)

    observable_request_handler.wait()
    assert observable_request_handler.event.name == EVENT_PROCESSING_REQUEST_OBSERVABLE
    assert AnalysisRequest.from_dict(observable_request_handler.event.args, system) == request

    result_handler = TestEventHandler()
    await system.register_event_handler(EVENT_PROCESSING_REQUEST_RESULT, result_handler)

    request.initialize_result()
    request.modified_observable.add_analysis(type=amt, details={"test": "test"})
    await system.process_analysis_request(request)

    result_handler.wait()
    assert result_handler.event.name == EVENT_PROCESSING_REQUEST_RESULT
    assert AnalysisRequest.from_dict(result_handler.event.args, system) == request
