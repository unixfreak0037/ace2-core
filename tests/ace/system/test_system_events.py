# vim: ts=4:sw=4:et:cc=120

import threading

import pytest

from ace.analysis import RootAnalysis, AnalysisModuleType
from ace.data_model import Event, ContentMetadata
from ace.system.alerting import submit_alert, register_alert_system, unregister_alert_system
from ace.system.analysis_module import register_analysis_module_type, delete_analysis_module_type
from ace.system.analysis_tracking import (
    track_root_analysis,
    delete_root_analysis,
    track_analysis_details,
    delete_analysis_details,
)
from ace.system.analysis_request import (
    track_analysis_request,
    delete_analysis_request,
    process_expired_analysis_requests,
    AnalysisRequest,
)
from ace.system.caching import generate_cache_key, cache_analysis_result
from ace.system.config import set_config
from ace.system.constants import (
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
from ace.system.events import register_event_handler, remove_event_handler, get_event_handlers, fire_event, EventHandler
from ace.system.processing import submit_analysis_request, process_analysis_request
from ace.system.storage import delete_content, store_content
from ace.system.work_queue import add_work_queue, delete_work_queue, put_work, get_work, get_next_analysis_request


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


@pytest.mark.integration
def test_EVENT_ANALYSIS_ROOT_NEW():
    handler = TestEventHandler()
    register_event_handler(EVENT_ANALYSIS_ROOT_NEW, handler)
    root = RootAnalysis()
    track_root_analysis(root)

    handler.wait()
    assert handler.event.name == EVENT_ANALYSIS_ROOT_NEW
    assert RootAnalysis.from_dict(handler.event.args) == root

    handler = TestEventHandler()
    register_event_handler(EVENT_ANALYSIS_ROOT_NEW, handler)
    # already tracked
    track_root_analysis(root)

    assert handler.event is None


@pytest.mark.integration
def test_EVENT_ANALYSIS_ROOT_MODIFIED():
    handler = TestEventHandler()
    register_event_handler(EVENT_ANALYSIS_ROOT_MODIFIED, handler)
    root = RootAnalysis()
    track_root_analysis(root)

    assert handler.event is None

    handler = TestEventHandler()
    register_event_handler(EVENT_ANALYSIS_ROOT_MODIFIED, handler)
    # already tracked so should fire as modified
    track_root_analysis(root)

    handler.wait()
    assert handler.event.name == EVENT_ANALYSIS_ROOT_MODIFIED
    assert RootAnalysis.from_dict(handler.event.args) == root


@pytest.mark.integration
def test_EVENT_ANALYSIS_ROOT_DELETED():
    root = RootAnalysis()
    track_root_analysis(root)
    handler = TestEventHandler()
    register_event_handler(EVENT_ANALYSIS_ROOT_DELETED, handler)
    delete_root_analysis(root)

    handler.wait()
    assert handler.event.name == EVENT_ANALYSIS_ROOT_DELETED
    assert handler.event.args == root.uuid

    # since the root was already deleted this should not fire twice
    handler = TestEventHandler()
    register_event_handler(EVENT_ANALYSIS_ROOT_DELETED, handler)
    delete_root_analysis(root)

    assert handler.event is None


@pytest.mark.integration
def test_EVENT_ANALYSIS_DETAILS_NEW():
    handler = TestEventHandler()
    register_event_handler(EVENT_ANALYSIS_DETAILS_NEW, handler)
    root = RootAnalysis(details={"test": "test"})
    track_root_analysis(root)
    track_analysis_details(root, root.uuid, root.details)

    handler.wait()
    assert handler.event.name == EVENT_ANALYSIS_DETAILS_NEW
    assert RootAnalysis.from_dict(handler.event.args[0]) == root
    assert handler.event.args[1] == root.uuid

    handler = TestEventHandler()
    register_event_handler(EVENT_ANALYSIS_DETAILS_NEW, handler)
    # already tracked
    track_analysis_details(root, root.uuid, root.details)

    assert handler.event is None


@pytest.mark.integration
def test_EVENT_ANALYSIS_DETAILS_MODIFIED():
    handler = TestEventHandler()
    register_event_handler(EVENT_ANALYSIS_DETAILS_MODIFIED, handler)
    root = RootAnalysis(details={"test": "test"})
    track_root_analysis(root)
    track_analysis_details(root, root.uuid, root.details)

    assert handler.event is None

    handler = TestEventHandler()
    register_event_handler(EVENT_ANALYSIS_DETAILS_MODIFIED, handler)
    track_analysis_details(root, root.uuid, root.details)

    handler.wait()
    assert handler.event.name == EVENT_ANALYSIS_DETAILS_MODIFIED
    assert RootAnalysis.from_dict(handler.event.args[0]) == root
    assert handler.event.args[1] == root.uuid


@pytest.mark.integration
def test_EVENT_ANALYSIS_DETAILS_DELETED():
    handler = TestEventHandler()
    root = RootAnalysis(details={"test": "test"})
    track_root_analysis(root)
    track_analysis_details(root, root.uuid, root.details)

    register_event_handler(EVENT_ANALYSIS_DETAILS_DELETED, handler)
    delete_analysis_details(root.uuid)

    handler.wait()
    assert handler.event.name == EVENT_ANALYSIS_DETAILS_DELETED
    assert handler.event.args == root.uuid

    handler = TestEventHandler()
    register_event_handler(EVENT_ANALYSIS_DETAILS_DELETED, handler)
    delete_analysis_details(root.uuid)

    assert handler.event is None


@pytest.mark.integration
def test_ALERT_SYSTEM_REGISTERED():
    handler = TestEventHandler()
    register_event_handler(EVENT_ALERT_SYSTEM_REGISTERED, handler)
    register_alert_system("test")

    handler.wait()
    assert handler.event.name == EVENT_ALERT_SYSTEM_REGISTERED
    assert handler.event.args == "test"

    handler = TestEventHandler()
    register_event_handler(EVENT_ALERT_SYSTEM_REGISTERED, handler)
    register_alert_system("test")
    assert handler.event is None


@pytest.mark.integration
def test_ALERT_SYSTEM_REGISTERED():
    register_alert_system("test")
    handler = TestEventHandler()
    register_event_handler(EVENT_ALERT_SYSTEM_UNREGISTERED, handler)

    unregister_alert_system("test")
    handler.wait()
    assert handler.event.name == EVENT_ALERT_SYSTEM_UNREGISTERED
    assert handler.event.args == "test"

    handler = TestEventHandler()
    register_event_handler(EVENT_ALERT_SYSTEM_UNREGISTERED, handler)
    unregister_alert_system("test")
    assert handler.event is None


@pytest.mark.integration
def test_EVENT_ALERT():
    register_alert_system("test")
    root = RootAnalysis()
    track_root_analysis(root)
    root.add_detection_point("test")

    handler = TestEventHandler()
    register_event_handler(EVENT_ALERT, handler)
    submit_alert(root)

    handler.wait()
    assert handler.event.name == EVENT_ALERT
    assert handler.event.args == root.uuid

    # event fires every time
    handler = TestEventHandler()
    register_event_handler(EVENT_ALERT, handler)
    submit_alert(root)

    handler.wait()
    assert handler.event.name == EVENT_ALERT
    assert handler.event.args == root.uuid


@pytest.mark.integration
def test_EVENT_AMT_NEW():
    handler = TestEventHandler()
    register_event_handler(EVENT_AMT_NEW, handler)

    amt = AnalysisModuleType("test", "")
    register_analysis_module_type(amt)

    handler.wait()
    assert handler.event.name == EVENT_AMT_NEW
    assert AnalysisModuleType.from_dict(handler.event.args) == amt

    handler = TestEventHandler()
    register_event_handler(EVENT_AMT_NEW, handler)

    # already registered so should not be new
    register_analysis_module_type(amt)

    assert handler.event is None


@pytest.mark.integration
def test_EVENT_AMT_MODIFIED():
    handler = TestEventHandler()
    register_event_handler(EVENT_AMT_MODIFIED, handler)

    amt = AnalysisModuleType("test", "")
    register_analysis_module_type(amt)

    assert handler.event is None

    handler = TestEventHandler()
    register_event_handler(EVENT_AMT_MODIFIED, handler)

    # still not modified yet
    register_analysis_module_type(amt)

    assert handler.event is None

    # modify version
    amt.version = "1.0.1"

    handler = TestEventHandler()
    register_event_handler(EVENT_AMT_MODIFIED, handler)

    # modified this time
    register_analysis_module_type(amt)

    handler.wait()
    assert handler.event.name == EVENT_AMT_MODIFIED
    assert AnalysisModuleType.from_dict(handler.event.args) == amt


@pytest.mark.integration
def test_EVENT_AMT_DELETED():
    handler = TestEventHandler()
    register_event_handler(EVENT_AMT_DELETED, handler)

    amt = AnalysisModuleType("test", "")
    register_analysis_module_type(amt)
    delete_analysis_module_type(amt)

    handler.wait()
    assert handler.event.name == EVENT_AMT_DELETED
    assert AnalysisModuleType.from_dict(handler.event.args) == amt

    handler = TestEventHandler()
    register_event_handler(EVENT_AMT_DELETED, handler)
    delete_analysis_module_type(amt)

    assert handler.event is None


@pytest.mark.integration
def test_EVENT_AR_NEW():
    handler = TestEventHandler()
    register_event_handler(EVENT_AR_NEW, handler)

    root = RootAnalysis()
    request = root.create_analysis_request()
    track_analysis_request(request)

    handler.wait()
    assert handler.event.name == EVENT_AR_NEW
    assert AnalysisRequest.from_dict(handler.event.args) == request

    handler = TestEventHandler()
    register_event_handler(EVENT_AR_NEW, handler)
    track_analysis_request(request)

    # you can re-track a request without harm
    handler.wait()
    assert handler.event.name == EVENT_AR_NEW
    assert AnalysisRequest.from_dict(handler.event.args) == request


@pytest.mark.integration
def test_EVENT_AR_DELETED():
    handler = TestEventHandler()
    register_event_handler(EVENT_AR_DELETED, handler)

    root = RootAnalysis()
    request = root.create_analysis_request()
    track_analysis_request(request)
    delete_analysis_request(request)

    handler.wait()
    assert handler.event.name == EVENT_AR_DELETED
    assert handler.event.args == request.id

    handler = TestEventHandler()
    register_event_handler(EVENT_AR_DELETED, handler)
    delete_analysis_request(request)
    assert handler.event is None


@pytest.mark.integration
def test_EVENT_AR_EXPIRED():
    handler = TestEventHandler()
    register_event_handler(EVENT_AR_EXPIRED, handler)

    amt = AnalysisModuleType(name="test", description="test", version="1.0.0", timeout=0, cache_ttl=600)
    register_analysis_module_type(amt)

    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    request = observable.create_analysis_request(amt)
    track_analysis_request(request)
    request.status = TRACKING_STATUS_ANALYZING
    track_analysis_request(request)

    process_expired_analysis_requests(amt)

    handler.wait()
    assert handler.event.name == EVENT_AR_EXPIRED
    assert AnalysisRequest.from_dict(handler.event.args) == request


@pytest.mark.integration
def test_EVENT_CACHE_NEW():
    handler = TestEventHandler()
    register_event_handler(EVENT_CACHE_NEW, handler)

    amt = AnalysisModuleType(name="test", description="", cache_ttl=600)
    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    request = observable.create_analysis_request(amt)
    request.initialize_result()
    analysis = request.modified_observable.add_analysis(type=amt)

    assert cache_analysis_result(request) is not None

    handler.wait()
    assert handler.event.name == EVENT_CACHE_NEW
    assert handler.event.args[0] == generate_cache_key(observable, amt)
    assert AnalysisRequest.from_dict(handler.event.args[1]) == request

    # we can potentially see duplicate cache hits
    handler = TestEventHandler()
    register_event_handler(EVENT_CACHE_NEW, handler)
    assert cache_analysis_result(request) is not None
    handler.wait()
    assert handler.event.name == EVENT_CACHE_NEW
    assert handler.event.args[0] == generate_cache_key(observable, amt)
    assert AnalysisRequest.from_dict(handler.event.args[1]) == request


@pytest.mark.integration
def test_EVENT_CONFIG_SET():
    handler = TestEventHandler()
    register_event_handler(EVENT_CONFIG_SET, handler)

    set_config("test", "value")
    handler.wait()
    assert handler.event.name == EVENT_CONFIG_SET
    assert handler.event.args[0] == "test"
    assert handler.event.args[1] == "value"

    # duplicate OK
    handler = TestEventHandler()
    register_event_handler(EVENT_CONFIG_SET, handler)
    set_config("test", "value")
    handler.wait()
    assert handler.event.name == EVENT_CONFIG_SET
    assert handler.event.args[0] == "test"
    assert handler.event.args[1] == "value"


@pytest.mark.integration
def test_EVENT_STORAGE_NEW():
    handler = TestEventHandler()
    register_event_handler(EVENT_STORAGE_NEW, handler)

    meta = ContentMetadata(name="test")
    sha256 = store_content("test", meta)

    handler.wait()
    assert handler.event.name == EVENT_STORAGE_NEW
    assert handler.event.args[0] == sha256
    assert ContentMetadata.parse_obj(handler.event.args[1]) == meta

    # duplicates are OK
    handler = TestEventHandler()
    register_event_handler(EVENT_STORAGE_NEW, handler)

    meta = ContentMetadata(name="test")
    sha256 = store_content("test", meta)

    handler.wait()
    assert handler.event.name == EVENT_STORAGE_NEW
    assert handler.event.args[0] == sha256
    assert ContentMetadata.parse_obj(handler.event.args[1]) == meta


@pytest.mark.integration
def test_EVENT_STORAGE_DELETED():
    handler = TestEventHandler()
    register_event_handler(EVENT_STORAGE_DELETED, handler)
    meta = ContentMetadata(name="test")
    sha256 = store_content("test", meta)
    delete_content(sha256)

    handler.wait()
    assert handler.event.name == EVENT_STORAGE_DELETED
    assert handler.event.args == sha256

    # duplicate does not fire event (already gone)
    handler = TestEventHandler()
    register_event_handler(EVENT_STORAGE_DELETED, handler)
    delete_content(sha256)
    assert handler.event is None


@pytest.mark.integration
def test_EVENT_WORK_QUEUE_NEW():
    handler = TestEventHandler()
    register_event_handler(EVENT_WORK_QUEUE_NEW, handler)

    add_work_queue("test")
    handler.wait()
    assert handler.event.name == EVENT_WORK_QUEUE_NEW
    assert handler.event.args == "test"

    # duplicate should not fire
    handler = TestEventHandler()
    register_event_handler(EVENT_WORK_QUEUE_NEW, handler)

    add_work_queue("test")
    assert handler.event is None


@pytest.mark.integration
def test_EVENT_WORK_QUEUE_DELETED():
    handler = TestEventHandler()
    register_event_handler(EVENT_WORK_QUEUE_DELETED, handler)

    add_work_queue("test")
    delete_work_queue("test")
    handler.wait()
    assert handler.event.name == EVENT_WORK_QUEUE_DELETED
    assert handler.event.args == "test"

    # duplicate should not fire
    handler = TestEventHandler()
    register_event_handler(EVENT_WORK_QUEUE_DELETED, handler)

    delete_work_queue("test")
    assert handler.event is None


@pytest.mark.integration
def test_EVENT_WORK_ADD():
    handler = TestEventHandler()
    register_event_handler(EVENT_WORK_ADD, handler)

    amt = AnalysisModuleType("test", "")
    register_analysis_module_type(amt)
    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    request = AnalysisRequest(root, observable, amt)
    submit_analysis_request(request)

    handler.wait()
    assert handler.event.name == EVENT_WORK_ADD
    assert handler.event.args[0] == amt.name
    assert AnalysisRequest.from_dict(handler.event.args[1]) == request


@pytest.mark.integration
def test_EVENT_WORK_REMOVE():
    handler = TestEventHandler()
    register_event_handler(EVENT_WORK_REMOVE, handler)

    amt = AnalysisModuleType("test", "")
    register_analysis_module_type(amt)
    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    request = AnalysisRequest(root, observable, amt)
    submit_analysis_request(request)
    work = get_work(amt, 0)

    handler.wait()
    assert handler.event.name == EVENT_WORK_REMOVE
    assert handler.event.args[0] == amt.name
    assert AnalysisRequest.from_dict(handler.event.args[1]) == work

    # can't get fired if you ain't got no work
    handler = TestEventHandler()
    register_event_handler(EVENT_WORK_REMOVE, handler)

    work = get_work(amt, 0)

    assert handler.event is None


@pytest.mark.integration
def test_EVENT_ANALYSIS_ROOT_EXPIRED():
    handler = TestEventHandler()
    register_event_handler(EVENT_ANALYSIS_ROOT_EXPIRED, handler)

    root = RootAnalysis(expires=True)
    root.submit()

    handler.wait()
    assert handler.event.name == EVENT_ANALYSIS_ROOT_EXPIRED
    assert RootAnalysis.from_dict(handler.event.args) == root


@pytest.mark.integration
def test_EVENT_CACHE_HIT():
    handler = TestEventHandler()
    register_event_handler(EVENT_CACHE_HIT, handler)

    amt = AnalysisModuleType("test", "", cache_ttl=60)
    register_analysis_module_type(amt)
    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    root_request = root.create_analysis_request()
    process_analysis_request(root_request)
    request = get_next_analysis_request("owner", amt, 0)
    request.initialize_result()
    request.modified_observable.add_analysis(type=amt, details={"test": "test"})
    process_analysis_request(request)
    assert handler.event is None

    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    root_request = root.create_analysis_request()
    process_analysis_request(root_request)

    handler.wait()
    assert handler.event.name == EVENT_CACHE_HIT
    assert RootAnalysis.from_dict(handler.event.args[0]) == root
    assert handler.event.args[1]["type"] == observable.type
    assert handler.event.args[1]["value"] == observable.value
    assert isinstance(AnalysisRequest.from_dict(handler.event.args[2]), AnalysisRequest)


@pytest.mark.integration
def test_EVENT_WORK_ASSIGNED():
    handler = TestEventHandler()
    register_event_handler(EVENT_WORK_ASSIGNED, handler)

    amt = AnalysisModuleType("test", "", cache_ttl=60)
    register_analysis_module_type(amt)
    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    root_request = root.create_analysis_request()
    process_analysis_request(root_request)
    request = get_next_analysis_request("owner", amt, 0)

    handler.wait()
    assert handler.event.name == EVENT_WORK_ASSIGNED
    assert AnalysisRequest.from_dict(handler.event.args) == request


@pytest.mark.integration
def test_EVENT_PROCESSING():
    root_handler = TestEventHandler()
    register_event_handler(EVENT_PROCESSING_REQUEST_ROOT, root_handler)

    observable_request_handler = TestEventHandler()
    register_event_handler(EVENT_PROCESSING_REQUEST_OBSERVABLE, observable_request_handler)

    amt = AnalysisModuleType("test", "", cache_ttl=60)
    register_analysis_module_type(amt)
    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    root_request = root.create_analysis_request()
    process_analysis_request(root_request)

    root_handler.wait()
    assert root_handler.event.name == EVENT_PROCESSING_REQUEST_ROOT
    assert AnalysisRequest.from_dict(root_handler.event.args) == root_request

    request = get_next_analysis_request("owner", amt, 0)

    observable_request_handler.wait()
    assert observable_request_handler.event.name == EVENT_PROCESSING_REQUEST_OBSERVABLE
    assert AnalysisRequest.from_dict(observable_request_handler.event.args) == request

    result_handler = TestEventHandler()
    register_event_handler(EVENT_PROCESSING_REQUEST_RESULT, result_handler)

    request.initialize_result()
    request.modified_observable.add_analysis(type=amt, details={"test": "test"})
    process_analysis_request(request)

    result_handler.wait()
    assert result_handler.event.name == EVENT_PROCESSING_REQUEST_RESULT
    assert AnalysisRequest.from_dict(result_handler.event.args) == request
