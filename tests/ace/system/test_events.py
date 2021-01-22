# vim: ts=4:sw=4:et:cc=120

import pytest

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
def test_event_handler():
    handler = TestEventHandler()
    register_event_handler("test", handler)
    fire_event("test", "test", kwarg1="test")
    assert handler.event == "test"
    assert handler.args[0] == "test"
    assert handler.kwargs["kwarg1"] == "test"

    handler.reset()
    remove_event_handler(handler)
    fire_event("test", "test", kwarg1="test")
    assert handler.event is None


@pytest.mark.integration
def test_event_remove_multiple():
    handler = TestEventHandler()
    register_event_handler("test_1", handler)
    register_event_handler("test_2", handler)
    fire_event("test_1", "test", kwarg1="test")
    assert handler.event == "test_1"
    handler.reset()
    fire_event("test_2", "test", kwarg1="test")
    assert handler.event == "test_2"
    handler.reset()
    remove_event_handler(handler, ["test_1"])
    fire_event("test_1", "test", kwarg1="test")
    assert handler.event is None
    fire_event("test_2", "test", kwarg1="test")
    assert handler.event == "test_2"


@pytest.mark.integration
def test_event_handle_exception():
    class TestExceptionHandler(TestEventHandler):
        def handle_event(self, event: str, *args, **kwargs):
            raise RuntimeError()

    handler = TestExceptionHandler()
    register_event_handler("test", handler)
    fire_event("test", "test", kwarg1="test")
    assert handler.event == "test"
    assert handler.exception is not None
    assert handler.args[0] == "test"
    assert handler.kwargs["kwarg1"] == "test"


