# vim: ts=4:sw=4:et:cc=120

import json

import pytest

from ace.system.events import register_event_handler, remove_event_handler, get_event_handlers, fire_event, EventHandler


class TestEventHandler(EventHandler):
    event = None
    exception = None
    event_args_json = None

    @property
    def event_args(self):
        return json.loads(self.event_args_json)

    def handle_event(self, event: str, event_args_json: str):
        self.event = event
        self.event_args_json = event_args_json

    def handle_exception(self, event: str, exception: Exception, event_args_json: str):
        self.event = event
        self.exception = exception
        self.event_args_json = event_args_json

    def reset(self):
        self.event = None
        self.exception = None
        self.event_args_json = None


@pytest.mark.integration
def test_event_handler():
    handler = TestEventHandler()
    register_event_handler("test", handler)
    args = ["test", {"kwarg1": "test"}]
    fire_event("test", args)
    assert handler.event == "test"
    assert handler.event_args == args

    handler.reset()
    remove_event_handler(handler)
    fire_event("test", args)
    assert handler.event is None


@pytest.mark.integration
def test_event_remove_multiple():
    handler = TestEventHandler()
    register_event_handler("test_1", handler)
    register_event_handler("test_2", handler)
    args = ["test", {"kwarg1": "test"}]
    fire_event("test_1", args)
    assert handler.event == "test_1"
    handler.reset()
    fire_event("test_2", args)
    assert handler.event == "test_2"
    handler.reset()
    remove_event_handler(handler, ["test_1"])
    fire_event("test_1", args)
    assert handler.event is None
    fire_event("test_2", args)
    assert handler.event == "test_2"


@pytest.mark.integration
def test_event_handle_exception():
    class TestExceptionHandler(TestEventHandler):
        def handle_event(self, event: str, event_args_json: str):
            raise RuntimeError()

    handler = TestExceptionHandler()
    register_event_handler("test", handler)
    args = ["test", {"kwarg1": "test"}]
    fire_event("test", args)
    assert handler.event == "test"
    assert handler.exception is not None
    assert handler.event_args == args
