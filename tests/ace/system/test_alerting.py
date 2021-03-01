# vim: ts=4:sw=4:et:cc=120

import threading

import pytest

from ace.analysis import RootAnalysis, AnalysisModuleType
from ace.system import get_system
from ace.system.analysis_module import register_analysis_module_type
from ace.system.alerting import (
    register_alert_system,
    unregister_alert_system,
    get_alert_count,
    submit_alert,
    get_alerts,
)
from ace.system.constants import EVENT_ALERT
from ace.system.events import Event, EventHandler, register_event_handler
from ace.system.exceptions import UnknownAlertSystemError
from ace.system.processing import process_analysis_request
from ace.system.work_queue import get_next_analysis_request


@pytest.mark.unit
def test_alert_system_registration():
    assert register_alert_system("test")
    # if it's already registered it should return False
    assert not register_alert_system("test")
    assert unregister_alert_system("test")
    # if it's already unregistered it should return False
    assert not unregister_alert_system("test")


@pytest.mark.unit
def test_alert_submission():
    root = RootAnalysis()
    # we have not registered an alert system yet so this should fail
    assert not submit_alert(root)
    register_alert_system("test")
    assert get_alert_count("test") == 0
    assert submit_alert(root)
    assert get_alert_count("test") == 1


@pytest.mark.unit
def test_multiple_alert_system_registration():
    assert register_alert_system("test_1")
    assert register_alert_system("test_2")
    root = RootAnalysis()
    assert submit_alert(root)
    assert get_alerts("test_1") == [root.uuid]
    assert get_alerts("test_2") == [root.uuid]


@pytest.mark.unit
def test_get_alerts():
    root = RootAnalysis()
    register_alert_system("test")
    assert submit_alert(root)
    assert get_alerts("test") == [root.uuid]
    assert get_alerts("test") == []
    assert submit_alert(root)
    assert submit_alert(root)
    assert get_alerts("test") == [root.uuid, root.uuid]
    assert get_alerts("test") == []


@pytest.mark.unit
def test_get_alerts_with_timeout():
    root = RootAnalysis()
    register_alert_system("test")
    assert submit_alert(root)
    assert get_alerts("test", timeout=1) == [root.uuid]
    assert get_alerts("test") == []

    # if there are two alerts then it takes two calls with a timeout
    assert submit_alert(root)
    assert submit_alert(root)

    assert get_alerts("test", timeout=1) == [root.uuid]
    assert get_alerts("test", timeout=1) == [root.uuid]
    assert get_alerts("test") == []


@pytest.mark.unit
def test_get_alerts_unknown_alert_system():
    with pytest.raises(UnknownAlertSystemError):
        get_alerts("test")

    with pytest.raises(UnknownAlertSystemError):
        get_alert_count("test")


@pytest.mark.integration
def test_root_detection():
    assert register_alert_system("test")
    root = RootAnalysis()
    root.add_detection_point("test")
    process_analysis_request(root.create_analysis_request())
    assert get_alerts("test") == [root.uuid]


@pytest.mark.integration
def test_observable_detection():
    assert register_alert_system("test")
    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    observable.add_detection_point("test")
    process_analysis_request(root.create_analysis_request())
    assert get_alerts("test") == [root.uuid]


@pytest.mark.integration
def test_analysis_detection():
    assert register_alert_system("test")
    amt = AnalysisModuleType("test", "")
    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    analysis = observable.add_analysis(type=amt)
    analysis.add_detection_point("test")
    process_analysis_request(root.create_analysis_request())
    assert get_alerts("test") == [root.uuid]


@pytest.mark.integration
def test_no_detection():
    assert register_alert_system("test")
    amt = AnalysisModuleType("test", "")
    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    analysis = observable.add_analysis(type=amt)
    process_analysis_request(root.create_analysis_request())
    assert not get_alerts("test")


@pytest.mark.integration
def test_analysis_result_detection():
    assert register_alert_system("test")
    amt = AnalysisModuleType("test", "")
    register_analysis_module_type(amt)
    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    process_analysis_request(root.create_analysis_request())
    assert not get_alerts("test")
    request = get_next_analysis_request("test", amt, 0)
    request.initialize_result()
    request.modified_observable.add_analysis(type=amt).add_detection_point("test")
    process_analysis_request(request)
    assert get_alerts("test") == [root.uuid]


@pytest.mark.system
def test_alert_collection_on_event():
    # alert management system registers for EVENT_ALERT
    # and then collects alerts when that fires
    assert register_alert_system("test")

    class TestEventHandler(EventHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.event = None
            self.sync = threading.Event()

        def handle_event(self, event: Event):
            self.event = event
            self.sync.set()

        def wait(self):
            if not self.sync.wait(3):
                raise RuntimeError("timed out")

    handler = TestEventHandler()
    register_event_handler(EVENT_ALERT, handler)

    amt = AnalysisModuleType("test", "")
    register_analysis_module_type(amt)
    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    process_analysis_request(root.create_analysis_request())
    request = get_next_analysis_request("test", amt, 0)
    request.initialize_result()
    request.modified_observable.add_analysis(type=amt).add_detection_point("test")
    process_analysis_request(request)

    handler.wait()
    assert handler.event.name == EVENT_ALERT
    assert handler.event.args == root.uuid
    assert get_alerts("test") == [root.uuid]
