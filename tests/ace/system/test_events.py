# vim: ts=4:sw=4:et:cc=120

import json
from dataclasses import dataclass

import pytest

from ace.analysis import RootAnalysis
from ace.data_model import Event
from ace.system.events import register_event_handler, remove_event_handler, get_event_handlers, fire_event, EventHandler


class TestEventHandler(EventHandler):
    event = None
    exception = None
    event_args_json = None

    @property
    def event_args(self):
        return json.loads(self.event_args_json)

    def handle_event(self, event: Event):
        self.event = event

    def handle_exception(self, event: Event, exception: Exception):
        self.event = event
        self.exception = exception

    def reset(self):
        self.event = None
        self.exception = None


@pytest.mark.unit
def test_event_serialization():
    # no args
    event = Event(name="test")
    target = Event.parse_obj(event.dict())
    assert event.name == target.name
    assert event.args == target.args
    assert not target.args

    # simple string args
    event = Event(name="test", args="test")
    target = Event.parse_obj(event.dict())
    assert event.name == target.name
    assert event.args == target.args
    assert target.args == "test"

    # complex args
    args = ["test", {"test": "test"}]
    event = Event(name="test", args=args)
    target = Event.parse_obj(event.dict())
    assert event.name == target.name
    assert event.args == target.args
    assert target.args == args

    # dataclass
    @dataclass
    class _test:
        my_field: [str] = "test"

    args = _test()
    event = Event(name="test", args=args)
    target = Event.parse_obj(event.dict())
    assert event.name == target.name
    assert event.args == target.args
    assert target.args.my_field == "test"

    # custom classes
    root = RootAnalysis()
    event = Event(name="test", args=root)
    target = Event.parse_obj(event.dict())
    assert event.name == target.name
    assert event.args == target.args
    assert target.args == root


@pytest.mark.integration
def test_event_handler():
    handler = TestEventHandler()
    register_event_handler("test", handler)
    args = ["test", {"kwarg1": "test"}]
    fire_event("test", args)
    assert handler.event.name == "test"
    assert handler.event.args == args

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
    assert handler.event.name == "test_1"
    handler.reset()
    fire_event("test_2", args)
    assert handler.event.name == "test_2"
    handler.reset()
    remove_event_handler(handler, ["test_1"])
    fire_event("test_1", args)
    assert handler.event is None
    fire_event("test_2", args)
    assert handler.event.name == "test_2"


@pytest.mark.integration
def test_event_handle_exception():
    class TestExceptionHandler(TestEventHandler):
        def handle_event(self, event: Event):
            raise RuntimeError()

    handler = TestExceptionHandler()
    register_event_handler("test", handler)
    args = ["test", {"kwarg1": "test"}]
    fire_event("test", args)
    assert handler.event.name == "test"
    assert handler.event.args == args
    assert handler.exception is not None
