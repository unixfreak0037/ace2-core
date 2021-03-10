# vim: ts=4:sw=4:et:cc=120

import json
import threading

from dataclasses import dataclass

import pytest

from ace.analysis import RootAnalysis
from ace.data_model import Event
from ace.system.events import EventHandler


class TestEventHandler(EventHandler):
    __test__ = False

    def __init__(self, *args, **kwargs):
        self.event = None
        self.exception = None
        self.event_args_json = None
        self.sync = threading.Event()
        self.count = 0

    @property
    def event_args(self):
        return json.loads(self.event_args_json)

    def handle_event(self, event: Event):
        self.event = event
        self.count += 1
        self.sync.set()

    def handle_exception(self, event: Event, exception: Exception):
        self.event = event
        self.exception = exception
        self.sync.set()

    def wait(self):
        if not self.sync.wait(3):
            raise RuntimeError("wait() timed out")

    def reset(self):
        self.count = 0
        self.event = None
        self.exception = None
        self.sync = threading.Event()


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


@pytest.mark.asyncio
@pytest.mark.integration
async def test_event_handler(system):
    handler = TestEventHandler()
    await system.register_event_handler("test", handler)
    args = ["test", {"kwarg1": "test"}]
    await system.fire_event("test", args)

    handler.wait()
    assert handler.event.name == "test"
    assert handler.event.args == args

    handler.reset()
    await system.remove_event_handler(handler)
    await system.fire_event("test", args)
    assert handler.event is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_event_multiple_handlers(system):
    handler_1 = TestEventHandler()
    await system.register_event_handler("test", handler_1)

    handler_2 = TestEventHandler()
    await system.register_event_handler("test", handler_2)

    args = ["test", {"kwarg1": "test"}]
    await system.fire_event("test", args)

    handler_1.wait()
    assert handler_1.event.name == "test"
    assert handler_1.event.args == args

    handler_2.wait()
    assert handler_2.event.name == "test"
    assert handler_2.event.args == args


@pytest.mark.asyncio
@pytest.mark.integration
async def test_event_handlers_add_fire_remove(system):
    # add a handler
    handler_1 = TestEventHandler()
    await system.register_event_handler("test", handler_1)

    # fire the event
    args = ["test", {"kwarg1": "test"}]
    await system.fire_event("test", args)

    # make sure it fired
    handler_1.wait()
    assert handler_1.event.name == "test"
    assert handler_1.event.args == args

    # add a handler for a different event
    handler_2 = TestEventHandler()
    await system.register_event_handler("test_2", handler_2)

    # fire the new event
    args = ["test_2", {"kwarg1": "test"}]
    await system.fire_event("test_2", args)

    # make sure it fired
    handler_2.wait()
    assert handler_2.event.name == "test_2"
    assert handler_2.event.args == args

    # delete the new handler
    await system.remove_event_handler(handler_2)

    # fire the event again (nothing to handle it)
    await system.fire_event("test_2", args)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_register_duplicate_handler(system):
    handler = TestEventHandler()
    await system.register_event_handler("test", handler)
    # registering it twice is OK but it should emit a warning
    await system.register_event_handler("test", handler)
    await system.fire_event("test")
    handler.wait()
    assert handler.event.name == "test"
    assert handler.count == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_event_remove_multiple(system):
    handler = TestEventHandler()
    await system.register_event_handler("test_1", handler)
    await system.register_event_handler("test_2", handler)
    args = ["test", {"kwarg1": "test"}]
    await system.fire_event("test_1", args)
    handler.wait()
    assert handler.event.name == "test_1"
    handler.reset()
    await system.fire_event("test_2", args)
    handler.wait()
    assert handler.event.name == "test_2"
    handler.reset()
    await system.remove_event_handler(handler, ["test_1"])
    await system.fire_event("test_1", args)
    assert handler.event is None
    await system.fire_event("test_2", args)
    handler.wait()
    assert handler.event.name == "test_2"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_event_handle_exception(system):
    class TestExceptionHandler(TestEventHandler):
        def handle_event(self, event: Event):
            raise RuntimeError()

    handler = TestExceptionHandler()
    await system.register_event_handler("test", handler)
    args = ["test", {"kwarg1": "test"}]
    await system.fire_event("test", args)
    handler.wait()
    assert handler.event.name == "test"
    assert handler.event.args == args
    assert handler.exception is not None


@pytest.mark.asyncio
@pytest.mark.system
async def test_event_distribution(system):
    handlers = [TestEventHandler() for _ in range(100)]
    for handler in handlers:
        await system.register_event_handler("test", handler)

    await system.fire_event("test")

    for handler in handlers:
        handler.wait()
        assert handler.event.name == "test"
        assert handler.count == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_event_handlers(system):
    assert not await system.get_event_handlers("test")
    handler = TestEventHandler()
    await system.register_event_handler("test", handler)
    assert await system.get_event_handlers("test") == [handler]
    handler = TestEventHandler()
    await system.register_event_handler("test", handler)
    assert len(await system.get_event_handlers("test")) == 2
