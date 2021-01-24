# vim: ts=4:sw=4:et:cc=120

import pytest

from ace.analysis import RootAnalysis
from ace.system.analysis_tracking import track_root_analysis, delete_root_analysis
from ace.system.constants import EVENT_ANALYSIS_ROOT_NEW, EVENT_ANALYSIS_ROOT_MODIFIED, EVENT_ANALYSIS_ROOT_DELETED, EVENT_ANALYSIS_DETAILS_NEW, EVENT_ANALYSIS_DETAILS_MODIFIED, EVENT_ANALYSIS_DETAILS_DELETED
from ace.system.events import register_event_handler, remove_event_handler, get_event_handlers, fire_event, EventHandler

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
    # no details are added so this event should not fire
    handler = TestEventHandler()
    register_event_handler(EVENT_ANALYSIS_DETAILS_NEW, handler)
    root = RootAnalysis()
    track_root_analysis(root)

    assert handler.event is None
    assert handler.args is None

    handler = TestEventHandler()
    register_event_handler(EVENT_ANALYSIS_ROOT_NEW, handler)
    # already tracked
    track_root_analysis(root)

    assert handler.event is None
    assert handler.args is None
