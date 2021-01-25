# vim: ts=4:sw=4:et:cc=120

import pytest

from ace.analysis import RootAnalysis, AnalysisModuleType
from ace.system.alerting import track_alert
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
)
from ace.system.caching import generate_cache_key, cache_analysis_result
from ace.system.config import set_config
from ace.system.constants import (
    EVENT_ALERT,
    EVENT_AMT_DELETED,
    EVENT_AMT_MODIFIED,
    EVENT_AMT_NEW,
    EVENT_ANALYSIS_DETAILS_DELETED,
    EVENT_ANALYSIS_DETAILS_MODIFIED,
    EVENT_ANALYSIS_DETAILS_NEW,
    EVENT_ANALYSIS_ROOT_DELETED,
    EVENT_ANALYSIS_ROOT_MODIFIED,
    EVENT_ANALYSIS_ROOT_NEW,
    EVENT_AR_DELETED,
    EVENT_AR_EXPIRED,
    EVENT_AR_NEW,
    EVENT_CACHE_NEW,
    EVENT_CONFIG_SET,
    EVENT_STORAGE_NEW,
    EVENT_STORAGE_DELETE,
    TRACKING_STATUS_ANALYZING,
)
from ace.system.events import register_event_handler, remove_event_handler, get_event_handlers, fire_event, EventHandler
from ace.system.storage import delete_content, store_content, ContentMetadata


class TestEventHandler(EventHandler):
    event = None
    exception = None
    args = None
    kwargs = None

    def handle_event(self, event: str, *args, **kwargs):
        self.event = event
        self.args = args
        self.kwargs = kwargs

    def handle_exception(self, event: str, exception: Exception, *args, **kwargs):
        self.event = event
        self.exception = exception
        self.args = args
        self.kwargs = kwargs

    def reset(self):
        self.event = None
        self.exception = None
        self.args = None
        self.kwargs = None


@pytest.mark.integration
def test_EVENT_ANALYSIS_ROOT_NEW():
    handler = TestEventHandler()
    register_event_handler(EVENT_ANALYSIS_ROOT_NEW, handler)
    root = RootAnalysis()
    track_root_analysis(root)

    assert handler.event == EVENT_ANALYSIS_ROOT_NEW
    assert handler.args[0] == root

    handler = TestEventHandler()
    register_event_handler(EVENT_ANALYSIS_ROOT_NEW, handler)
    # already tracked
    track_root_analysis(root)

    assert handler.event is None
    assert handler.args is None


@pytest.mark.integration
def test_EVENT_ANALYSIS_ROOT_MODIFIED():
    handler = TestEventHandler()
    register_event_handler(EVENT_ANALYSIS_ROOT_MODIFIED, handler)
    root = RootAnalysis()
    track_root_analysis(root)

    assert handler.event is None
    assert handler.args is None

    handler = TestEventHandler()
    register_event_handler(EVENT_ANALYSIS_ROOT_MODIFIED, handler)
    # already tracked so should fire as modified
    track_root_analysis(root)

    assert handler.event == EVENT_ANALYSIS_ROOT_MODIFIED
    assert handler.args[0] == root


@pytest.mark.integration
def test_EVENT_ANALYSIS_ROOT_DELETED():
    root = RootAnalysis()
    track_root_analysis(root)
    handler = TestEventHandler()
    register_event_handler(EVENT_ANALYSIS_ROOT_DELETED, handler)
    delete_root_analysis(root)

    assert handler.event == EVENT_ANALYSIS_ROOT_DELETED
    assert handler.args[0] == root.uuid

    # since the root was already deleted this should not fire twice
    handler = TestEventHandler()
    register_event_handler(EVENT_ANALYSIS_ROOT_DELETED, handler)
    delete_root_analysis(root)

    assert handler.event is None
    assert handler.args is None


@pytest.mark.integration
def test_EVENT_ANALYSIS_DETAILS_NEW():
    handler = TestEventHandler()
    register_event_handler(EVENT_ANALYSIS_DETAILS_NEW, handler)
    root = RootAnalysis(details={"test": "test"})
    track_root_analysis(root)
    track_analysis_details(root, root.uuid, root.details)

    assert handler.event == EVENT_ANALYSIS_DETAILS_NEW
    assert handler.args[0] == root
    assert handler.args[1] == root.uuid

    handler = TestEventHandler()
    register_event_handler(EVENT_ANALYSIS_DETAILS_NEW, handler)
    # already tracked
    track_analysis_details(root, root.uuid, root.details)

    assert handler.event is None
    assert handler.args is None


@pytest.mark.integration
def test_EVENT_ANALYSIS_DETAILS_MODIFIED():
    handler = TestEventHandler()
    register_event_handler(EVENT_ANALYSIS_DETAILS_MODIFIED, handler)
    root = RootAnalysis(details={"test": "test"})
    track_root_analysis(root)
    track_analysis_details(root, root.uuid, root.details)

    assert handler.event is None
    assert handler.args is None

    handler = TestEventHandler()
    register_event_handler(EVENT_ANALYSIS_DETAILS_MODIFIED, handler)
    track_analysis_details(root, root.uuid, root.details)

    assert handler.event == EVENT_ANALYSIS_DETAILS_MODIFIED
    assert handler.args[0] == root
    assert handler.args[1] == root.uuid


@pytest.mark.integration
def test_EVENT_ANALYSIS_DETAILS_DELETED():
    handler = TestEventHandler()
    root = RootAnalysis(details={"test": "test"})
    track_root_analysis(root)
    track_analysis_details(root, root.uuid, root.details)

    register_event_handler(EVENT_ANALYSIS_DETAILS_DELETED, handler)
    delete_analysis_details(root.uuid)

    assert handler.event == EVENT_ANALYSIS_DETAILS_DELETED
    assert handler.args[0] == root.uuid

    handler = TestEventHandler()
    register_event_handler(EVENT_ANALYSIS_DETAILS_DELETED, handler)
    delete_analysis_details(root.uuid)

    assert handler.event is None
    assert handler.args is None


@pytest.mark.integration
def test_EVENT_ALERT():
    root = RootAnalysis()
    track_root_analysis(root)
    root.add_detection_point("test")

    handler = TestEventHandler()
    register_event_handler(EVENT_ALERT, handler)
    track_alert(root)

    assert handler.event == EVENT_ALERT
    assert handler.args[0] == root

    # event fires every time
    handler = TestEventHandler()
    register_event_handler(EVENT_ALERT, handler)
    track_alert(root)

    assert handler.event == EVENT_ALERT
    assert handler.args[0] == root


@pytest.mark.integration
def test_EVENT_AMT_NEW():
    handler = TestEventHandler()
    register_event_handler(EVENT_AMT_NEW, handler)

    amt = AnalysisModuleType("test", "")
    register_analysis_module_type(amt)

    assert handler.event == EVENT_AMT_NEW
    assert handler.args[0] == amt

    handler = TestEventHandler()
    register_event_handler(EVENT_AMT_NEW, handler)

    # already registered so should not be new
    register_analysis_module_type(amt)

    assert handler.event is None
    assert handler.args is None


@pytest.mark.integration
def test_EVENT_AMT_MODIFIED():
    handler = TestEventHandler()
    register_event_handler(EVENT_AMT_MODIFIED, handler)

    amt = AnalysisModuleType("test", "")
    register_analysis_module_type(amt)

    assert handler.event is None
    assert handler.args is None

    handler = TestEventHandler()
    register_event_handler(EVENT_AMT_MODIFIED, handler)

    # still not modified yet
    register_analysis_module_type(amt)

    assert handler.event is None
    assert handler.args is None

    # modify version
    amt.version = "1.0.1"

    handler = TestEventHandler()
    register_event_handler(EVENT_AMT_MODIFIED, handler)

    # modified this time
    register_analysis_module_type(amt)

    assert handler.event == EVENT_AMT_MODIFIED
    assert handler.args[0] == amt


@pytest.mark.integration
def test_EVENT_AMT_DELETED():
    handler = TestEventHandler()
    register_event_handler(EVENT_AMT_DELETED, handler)

    amt = AnalysisModuleType("test", "")
    register_analysis_module_type(amt)
    delete_analysis_module_type(amt)

    assert handler.event == EVENT_AMT_DELETED
    assert handler.args[0] == amt

    handler = TestEventHandler()
    register_event_handler(EVENT_AMT_DELETED, handler)
    delete_analysis_module_type(amt)

    assert handler.event is None
    assert handler.args is None


@pytest.mark.integration
def test_EVENT_AR_NEW():
    handler = TestEventHandler()
    register_event_handler(EVENT_AR_NEW, handler)

    root = RootAnalysis()
    request = root.create_analysis_request()
    track_analysis_request(request)

    assert handler.event == EVENT_AR_NEW
    assert handler.args[0] == request

    handler = TestEventHandler()
    register_event_handler(EVENT_AR_NEW, handler)
    track_analysis_request(request)

    # you can re-track a request without harm
    assert handler.event == EVENT_AR_NEW
    assert handler.args[0] == request


@pytest.mark.integration
def test_EVENT_AR_DELETED():
    handler = TestEventHandler()
    register_event_handler(EVENT_AR_DELETED, handler)

    root = RootAnalysis()
    request = root.create_analysis_request()
    track_analysis_request(request)
    delete_analysis_request(request)

    assert handler.event == EVENT_AR_DELETED
    assert handler.args[0] == request.id

    handler = TestEventHandler()
    register_event_handler(EVENT_AR_DELETED, handler)
    delete_analysis_request(request)
    assert handler.event is None
    assert handler.args is None


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

    process_expired_analysis_requests()

    assert handler.event == EVENT_AR_EXPIRED
    assert handler.args[0] == request


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

    assert handler.event == EVENT_CACHE_NEW
    assert handler.args[0] == generate_cache_key(observable, amt)
    assert handler.args[1] == request

    # we can potentially see duplicate cache hits
    handler = TestEventHandler()
    register_event_handler(EVENT_CACHE_NEW, handler)
    assert cache_analysis_result(request) is not None
    assert handler.event == EVENT_CACHE_NEW
    assert handler.args[0] == generate_cache_key(observable, amt)
    assert handler.args[1] == request


@pytest.mark.integration
def test_EVENT_CONFIG_SET():
    handler = TestEventHandler()
    register_event_handler(EVENT_CONFIG_SET, handler)

    set_config("test", "value")
    assert handler.event == EVENT_CONFIG_SET
    assert handler.args[0] == "test"
    assert handler.args[1] == "value"

    # duplicate OK
    handler = TestEventHandler()
    register_event_handler(EVENT_CONFIG_SET, handler)
    set_config("test", "value")
    assert handler.event == EVENT_CONFIG_SET
    assert handler.args[0] == "test"
    assert handler.args[1] == "value"


@pytest.mark.integration
def test_EVENT_STORAGE_NEW():
    handler = TestEventHandler()
    register_event_handler(EVENT_STORAGE_NEW, handler)

    meta = ContentMetadata("test")
    sha256 = store_content("test", meta)

    assert handler.event == EVENT_STORAGE_NEW
    assert handler.args[0] == sha256
    assert handler.args[1] == meta

    # duplicates are OK
    handler = TestEventHandler()
    register_event_handler(EVENT_STORAGE_NEW, handler)

    meta = ContentMetadata("test")
    sha256 = store_content("test", meta)

    assert handler.event == EVENT_STORAGE_NEW
    assert handler.args[0] == sha256
    assert handler.args[1] == meta


@pytest.mark.integration
def test_EVENT_STORAGE_DELETE():
    handler = TestEventHandler()
    register_event_handler(EVENT_STORAGE_DELETE, handler)
    meta = ContentMetadata("test")
    sha256 = store_content("test", meta)
    delete_content(sha256)

    assert handler.event == EVENT_STORAGE_DELETE
    assert handler.args[0] == sha256

    # duplicate does not fire event (already gone)
    handler = TestEventHandler()
    register_event_handler(EVENT_STORAGE_DELETE, handler)
    delete_content(sha256)
    assert handler.event is None
    assert handler.args is None
