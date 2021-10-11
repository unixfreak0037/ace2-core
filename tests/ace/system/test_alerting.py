# vim: ts=4:sw=4:et:cc=120

import asyncio

import pytest

from ace.analysis import RootAnalysis, AnalysisModuleType
from ace.system.distributed import app
from tests.systems import RemoteACETestSystem

# from ace.system import get_system
# from ace.system.analysis_module import register_analysis_module_type
# from ace.system.alerting import (
# register_alert_system,
# unregister_alert_system,
# get_alert_count,
# submit_alert,
# get_alerts,
# )
from ace.constants import EVENT_ALERT
from ace.system.events import Event, EventHandler  # , register_event_handler
from ace.exceptions import UnknownAlertSystemError

# from ace.system.processing import process_analysis_request
# from ace.system.work_queue import get_next_analysis_request


@pytest.mark.asyncio
@pytest.mark.unit
async def test_alert_system_registration(system):
    assert await system.register_alert_system("test")
    # if it's already registered it should return False
    assert not await system.register_alert_system("test")
    assert await system.unregister_alert_system("test")
    # if it's already unregistered it should return False
    assert not await system.unregister_alert_system("test")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_alert_submission(system):
    root = system.new_root()
    # we have not registered an alert system yet so this should fail
    assert not await system.submit_alert(root)
    await system.register_alert_system("test")
    assert await system.get_alert_count("test") == 0
    assert await system.submit_alert(root)
    assert await system.get_alert_count("test") == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_multiple_alert_system_registration(system):
    assert await system.register_alert_system("test_1")
    assert await system.register_alert_system("test_2")
    root = system.new_root()
    assert await system.submit_alert(root)
    assert await system.get_alerts("test_1") == [root.uuid]
    assert await system.get_alerts("test_2") == [root.uuid]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_alerts(system):
    root = system.new_root()
    await system.register_alert_system("test")
    assert await system.submit_alert(root)
    assert await system.get_alerts("test") == [root.uuid]
    assert await system.get_alerts("test") == []
    assert await system.submit_alert(root)
    assert await system.submit_alert(root)
    assert await system.get_alerts("test") == [root.uuid, root.uuid]
    assert await system.get_alerts("test") == []


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_alerts_with_timeout(system):
    root = system.new_root()
    await system.register_alert_system("test")
    assert await system.submit_alert(root)
    assert await system.get_alerts("test", timeout=1) == [root.uuid]
    assert await system.get_alerts("test") == []

    # if there are two alerts then it takes two calls with a timeout
    assert await system.submit_alert(root)
    assert await system.submit_alert(root)

    assert await system.get_alerts("test", timeout=1) == [root.uuid]
    assert await system.get_alerts("test", timeout=1) == [root.uuid]
    assert await system.get_alerts("test") == []


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_alerts_unknown_alert_system(system):
    with pytest.raises(UnknownAlertSystemError):
        await system.get_alerts("test")

    with pytest.raises(UnknownAlertSystemError):
        await system.get_alert_count("test")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_root_detection(system):
    assert await system.register_alert_system("test")
    assert await system.get_alert_count("test") == 0
    root = system.new_root()
    root.add_detection_point("test")
    # XXX ??? why is this resetting the redis database?
    await system.process_analysis_request(root.create_analysis_request())
    assert await system.get_alert_count("test") == 1
    assert await system.get_alerts("test") == [root.uuid]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_observable_detection(system):
    assert await system.register_alert_system("test")
    root = system.new_root()
    observable = root.add_observable("test", "test")
    observable.add_detection_point("test")
    await system.process_analysis_request(root.create_analysis_request())
    assert await system.get_alerts("test") == [root.uuid]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_analysis_detection(system):
    assert await system.register_alert_system("test")
    amt = AnalysisModuleType("test", "")
    root = system.new_root()
    observable = root.add_observable("test", "test")
    analysis = observable.add_analysis(type=amt)
    analysis.add_detection_point("test")
    await system.process_analysis_request(root.create_analysis_request())
    assert await system.get_alerts("test") == [root.uuid]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_no_detection(system):
    assert await system.register_alert_system("test")
    amt = AnalysisModuleType("test", "")
    root = system.new_root()
    observable = root.add_observable("test", "test")
    analysis = observable.add_analysis(type=amt)
    await system.process_analysis_request(root.create_analysis_request())
    assert not await system.get_alerts("test")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_analysis_result_detection(system):
    assert await system.register_alert_system("test")
    amt = AnalysisModuleType("test", "")
    await system.register_analysis_module_type(amt)
    root = system.new_root()
    observable = root.add_observable("test", "test")
    await system.process_analysis_request(root.create_analysis_request())
    assert not await system.get_alerts("test")
    request = await system.get_next_analysis_request("test", amt, 0)
    request.initialize_result()
    request.modified_observable.add_analysis(type=amt).add_detection_point("test")
    await system.process_analysis_request(request)
    assert await system.get_alerts("test") == [root.uuid]


@pytest.mark.asyncio
@pytest.mark.system
async def test_alert_collection_on_event(system):
    # alert management system registers for EVENT_ALERT
    # and then collects alerts when that fires
    assert await system.register_alert_system("test")

    class TestEventHandler(EventHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.event = None
            self.sync = asyncio.Event()

        async def handle_event(self, event: Event):
            self.event = event
            self.sync.set()

        async def wait(self):
            if not await self.sync.wait():
                raise RuntimeError("timed out")

    handler = TestEventHandler()
    await system.register_event_handler(EVENT_ALERT, handler)

    amt = AnalysisModuleType("test", "")
    await system.register_analysis_module_type(amt)
    root = system.new_root()
    observable = root.add_observable("test", "test")
    await system.process_analysis_request(root.create_analysis_request())
    request = await system.get_next_analysis_request("test", amt, 0)
    request.initialize_result()
    request.modified_observable.add_analysis(type=amt).add_detection_point("test")
    await system.process_analysis_request(request)

    await handler.wait()
    assert handler.event.name == EVENT_ALERT
    assert handler.event.args == root.uuid
    assert await system.get_alerts("test") == [root.uuid]
