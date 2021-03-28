# vim: ts=4:sw=4:et:cc=120
#

import asyncio

import ace.analysis

from ace.analysis import RootAnalysis, Observable, AnalysisModuleType, Analysis
from ace.system import get_logger
from ace.constants import EVENT_ANALYSIS_ROOT_COMPLETED
from ace.system.events import EventHandler, Event
from ace.module.base import AnalysisModule, AsyncAnalysisModule
from ace.module.manager import AnalysisModuleManager, CONCURRENCY_MODE_PROCESS, CONCURRENCY_MODE_THREADED

import pytest


@pytest.mark.asyncio
@pytest.mark.system
async def test_basic_analysis_async(system):

    # basic analysis module
    class TestAsyncAnalysisModule(AsyncAnalysisModule):
        # define the type for this analysis module
        type = AnalysisModuleType("test", "")

        # define it as an async module
        async def execute_analysis(self, root, observable, analysis):
            analysis.set_details({"test": "test"})
            analysis.add_observable("test", "hello")
            return True

    # create an instance of it
    module = TestAsyncAnalysisModule()

    # register the type to the core
    await system.register_analysis_module_type(module.type)

    # submit a root for analysis so we create a new job
    root = system.new_root()
    observable = root.add_observable("test", "test")
    await root.submit()

    # create a new manager to run our analysis modules
    manager = AnalysisModuleManager(system)
    manager.add_module(module)
    await manager.run_once()

    # check the results in the core
    root = await system.get_root_analysis(root)
    observable = root.get_observable(observable)
    analysis = observable.get_analysis(module.type)
    assert analysis
    assert await analysis.get_details() == {"test": "test"}
    assert analysis.observables[0] == ace.analysis.Observable("test", "hello")


class TestSyncAnalysisModule(AnalysisModule):
    __test__ = False

    # define the type for this analysis module
    type = AnalysisModuleType("test", "")

    # define it as an sync module
    def execute_analysis(self, root, observable, analysis):
        analysis.set_details({"test": "test"})
        analysis.add_observable("test", "hello")
        return True


@pytest.mark.parametrize("concurrency_mode", [CONCURRENCY_MODE_THREADED, CONCURRENCY_MODE_PROCESS])
@pytest.mark.asyncio
@pytest.mark.system
async def test_basic_analysis_sync(concurrency_mode, system):

    # create an instance of it
    module = TestSyncAnalysisModule()

    # register the type to the core
    await system.register_analysis_module_type(module.type)

    # submit a root for analysis so we create a new job
    root = system.new_root()
    observable = root.add_observable("test", "test")
    await root.submit()

    # create a new manager to run our analysis modules
    manager = AnalysisModuleManager(system, concurrency_mode=concurrency_mode)
    manager.add_module(module)
    await manager.run_once()

    # check the results in the core
    root = await system.get_root_analysis(root)
    observable = root.get_observable(observable)
    analysis = observable.get_analysis(module.type)
    assert analysis
    assert await analysis.get_details() == {"test": "test"}
    assert analysis.observables[0] == ace.analysis.Observable("test", "hello")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_force_stop_stuck_async_task(system):
    control = asyncio.Event()

    class CustomAnalysisModule(AsyncAnalysisModule):
        async def execute_analysis(self, root, observable, analysis):
            nonlocal control
            control.set()
            # get stuck
            import sys

            await asyncio.sleep(sys.maxsize)

    # register the type to the core
    amt = AnalysisModuleType("test", "")
    await system.register_analysis_module_type(amt)

    manager = AnalysisModuleManager(system)
    module = CustomAnalysisModule(amt)
    manager.add_module(module)

    root = system.new_root()
    observable = root.add_observable("test", "test")
    await root.submit()

    async def _cancel():
        nonlocal control
        nonlocal manager
        await control.wait()
        manager.force_stop()

    cancel_task = asyncio.get_event_loop().create_task(_cancel())
    await manager.run()
    await cancel_task


class StuckAnalysisModule(AnalysisModule):
    def execute_analysis(self, root, observable, analysis):
        # get stuck
        import time, sys

        time.sleep(1000)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_force_stop_stuck_sync_task(system):
    # register the type to the core
    amt = AnalysisModuleType("test", "")
    await system.register_analysis_module_type(amt)

    manager = AnalysisModuleManager(system, concurrency_mode=CONCURRENCY_MODE_PROCESS)
    module = StuckAnalysisModule(amt)
    manager.add_module(module)

    root = system.new_root()
    observable = root.add_observable("test", "test")
    await root.submit()

    async def _cancel():
        nonlocal manager
        manager.force_stop()

    manager_task = asyncio.get_event_loop().create_task(manager.run())
    await asyncio.wait([manager_task], timeout=0.01)
    cancel_task = asyncio.get_event_loop().create_task(_cancel())
    await manager_task
    await cancel_task


@pytest.mark.asyncio
@pytest.mark.integration
async def test_raised_exception_during_async_analysis(system):
    class CustomAnalysisModule(AsyncAnalysisModule):
        async def execute_analysis(self, root, observable, analysis):
            raise RuntimeError("failure")

    amt = AnalysisModuleType("test", "")
    await system.register_analysis_module_type(amt)

    manager = AnalysisModuleManager(system)
    module = CustomAnalysisModule(amt)
    manager.add_module(module)

    root = system.new_root()
    observable = root.add_observable("test", "test")
    await root.submit()

    await manager.run_once()

    root = await system.get_root_analysis(root)
    observable = root.get_observable(observable)
    analysis = observable.get_analysis(amt)

    assert analysis.error_message == "testv1.0.0 failed analyzing type test value test: failure"
    assert analysis.stack_trace


class FailingAnalysisModule(AnalysisModule):
    def execute_analysis(self, root, observable, analysis):
        raise RuntimeError("failure")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_raised_exception_during_sync_analysis(system):
    amt = AnalysisModuleType("test", "")
    await system.register_analysis_module_type(amt)

    manager = AnalysisModuleManager(system)
    module = FailingAnalysisModule(amt)
    manager.add_module(module)

    root = system.new_root()
    observable = root.add_observable("test", "test")
    await root.submit()

    await manager.run_once()

    root = await system.get_root_analysis(root)
    observable = root.get_observable(observable)
    analysis = observable.get_analysis(amt)

    assert analysis.error_message == "testv1.0.0 failed analyzing type test value test: failure"
    assert analysis.stack_trace


class CrashingAnalysisModule(AnalysisModule):
    def execute_analysis(self, root, observable, analysis):
        import os, signal

        if observable.value == "crash":
            os.kill(os.getpid(), signal.SIGKILL)
        else:
            analysis.set_details({"test": "test"})


class SimpleSyncAnalysisModule(AnalysisModule):
    def execute_analysis(self, root, observable, analysis):
        analysis.set_details({"test": "test"})


#
# XXX this test has a timing issue
#


@pytest.mark.asyncio
@pytest.mark.integration
async def test_crashing_sync_analysis_module(system):

    import threading

    sync = threading.Event()

    class CustomEventHandler(EventHandler):
        def handle_event(self, event: Event):
            sync.set()

        def handle_exception(self, event: str, exception: Exception):
            pass

    await system.register_event_handler(EVENT_ANALYSIS_ROOT_COMPLETED, CustomEventHandler())

    amt_crashing = AnalysisModuleType("crash_test", "")
    amt_ok = AnalysisModuleType("ok", "")
    await system.register_analysis_module_type(amt_crashing)
    await system.register_analysis_module_type(amt_ok)

    # this is only supported in CONCURRENCY_MODE_PROCESS
    manager = AnalysisModuleManager(system, concurrency_mode=CONCURRENCY_MODE_PROCESS)
    crashing_module = CrashingAnalysisModule(amt_crashing)
    ok_module = SimpleSyncAnalysisModule(amt_ok)

    manager.add_module(crashing_module)
    manager.add_module(ok_module)

    root = system.new_root()
    observable = root.add_observable("test", "crash")
    await root.submit()

    await manager.run_once()

    # wait for analysis to complete
    assert sync.wait(3)

    root = await system.get_root_analysis(root)
    observable = root.get_observable(observable)
    analysis = observable.get_analysis(amt_crashing)

    assert analysis.error_message == "crash_testv1.0.0 process crashed when analyzing type test value crash"
    assert analysis.stack_trace

    observable = root.get_observable(observable)
    analysis = observable.get_analysis(amt_ok)

    # this one may or may not work depending on if you're using a local or remote api client
    assert (
        analysis.error_message == "okv1.0.0 process crashed when analyzing type test value crash"
        and analysis.stack_trace
    ) or await analysis.get_details() == {"test": "test"}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_upgraded_version_analysis_module(system):
    # NOTE for this one we don't need to test both sync and async because
    # this check comes before analysis module execution (same for both)
    step_1 = asyncio.Event()

    class CustomAnalysisModule(AnalysisModule):
        def execute_analysis(self, root, observable, analysis):
            nonlocal step_1
            analysis.set_details({"version": self.type.version})
            if not step_1.is_set():
                step_1.set()
                return

    amt = AnalysisModuleType("test", "", version="1.0.0")
    await system.register_analysis_module_type(amt)

    manager = AnalysisModuleManager(system)
    module = CustomAnalysisModule(type=amt)
    manager.add_module(module)

    root = system.new_root()
    observable = root.add_observable("test", "test")
    await root.submit()

    root_2 = system.new_root()
    observable_2 = root_2.add_observable("test", "test")

    async def _upgrade():
        nonlocal step_1
        nonlocal root_2
        await step_1.wait()
        updated_amt = AnalysisModuleType("test", "", version="1.0.1")
        await system.register_analysis_module_type(updated_amt)
        await root_2.submit()

    upgrade_task = asyncio.create_task(_upgrade())
    await manager.run()
    await upgrade_task

    # in this case the version mismatch just causes the manger to exit
    root = await system.get_root_analysis(root_2)
    observable = root.get_observable(observable)
    # so no analysis should be seen
    assert observable.get_analysis(amt) is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_upgraded_extended_version_async_analysis_module(system):
    """Tests the ability of an analysis module to update extended version data."""

    #
    # in this case the first call to get_next_analysis_request fails
    # but the module.upgrade() is called
    # since the work task is not acquired it stays in the queue
    # until the event_loop comes back around with the correct extended version data
    #

    step_1 = asyncio.Event()
    step_2 = asyncio.Event()

    class CustomAnalysisModule(AsyncAnalysisModule):
        async def execute_analysis(self, root, observable, analysis):
            nonlocal step_1
            analysis.set_details({"extended_version": self.type.extended_version})
            if not step_1.is_set():
                step_1.set()
                return

            step_2.set()

        async def upgrade(self):
            self.type.extended_version = ["intel:v2"]

    amt = AnalysisModuleType("test", "", extended_version=["intel:v1"])
    await system.register_analysis_module_type(amt)

    manager = AnalysisModuleManager(system)
    module = CustomAnalysisModule(type=amt)
    manager.add_module(module)

    root = system.new_root()
    observable = root.add_observable("test", "test")
    await root.submit()

    root_2 = system.new_root()
    observable_2 = root_2.add_observable("test", "test")

    async def _update_intel():
        nonlocal step_1
        nonlocal root_2
        await step_1.wait()
        # update the extended version data for this module type
        updated_amt = AnalysisModuleType("test", "", extended_version=["intel:v2"])
        await system.register_analysis_module_type(updated_amt)
        await root_2.submit()

    async def _shutdown():
        nonlocal step_2
        nonlocal manager
        await step_2.wait()
        manager.stop()

    upgrade_task = asyncio.create_task(_update_intel())
    shutdown_task = asyncio.create_task(_shutdown())
    await manager.run()
    await upgrade_task
    await shutdown_task

    root = await system.get_root_analysis(root_2)
    observable = root.get_observable(observable)
    assert (await observable.get_analysis(amt).get_details())["extended_version"] == ["intel:v2"]


class UpgradableAnalysisModule(AnalysisModule):
    def execute_analysis(self, root, observable, analysis):
        analysis.set_details({"extended_version": self.type.extended_version})

    def upgrade(self):
        self.type.extended_version = ["intel:v2"]


@pytest.mark.parametrize("concurrency_mode", [CONCURRENCY_MODE_THREADED, CONCURRENCY_MODE_PROCESS])
@pytest.mark.asyncio
@pytest.mark.integration
async def test_upgraded_extended_version_sync_analysis_module(concurrency_mode, system):
    """Tests the ability of a sync analysis module to update extended version data."""

    amt = AnalysisModuleType("test", "", extended_version=["intel:v1"])
    await system.register_analysis_module_type(amt)

    # we want to bail after the first execution of the module
    class CustomAnalysisModuleManager(AnalysisModuleManager):
        async def execute_module(self, *args, **kwargs):
            try:
                result = await AnalysisModuleManager.execute_module(self, *args, **kwargs)
            finally:
                self.shutdown = True

            return result

    manager = CustomAnalysisModuleManager(system, concurrency_mode=concurrency_mode)
    module = UpgradableAnalysisModule(type=amt)
    manager.add_module(module)

    root = system.new_root()
    observable = root.add_observable("test", "test")

    async def _update_intel():
        nonlocal manager
        # wait for the event loop to start
        await manager.event_loop_starting_event.wait()
        # update the extended version data for this module type
        updated_amt = AnalysisModuleType("test", "", extended_version=["intel:v2"])
        await system.register_analysis_module_type(updated_amt)
        # and then submit for analysis
        await root.submit()

    upgrade_task = asyncio.create_task(_update_intel())
    await manager.run()
    await upgrade_task

    root = await system.get_root_analysis(root)
    observable = root.get_observable(observable)
    assert (await observable.get_analysis(amt).get_details())["extended_version"] == ["intel:v2"]


@pytest.mark.parametrize("concurrency_mode", [CONCURRENCY_MODE_THREADED, CONCURRENCY_MODE_PROCESS])
@pytest.mark.asyncio
@pytest.mark.integration
async def test_upgrade_analysis_module_failure(concurrency_mode, system):

    amt = AnalysisModuleType("test", "", extended_version=["intel:v1"])
    await system.register_analysis_module_type(amt)

    class CustomAnalysisModule(AnalysisModule):
        async def execute_analysis(self, *args, **kwargs):
            pass

        async def upgrade(self):
            raise RuntimeError()

    manager = AnalysisModuleManager(system, concurrency_mode=concurrency_mode)
    module = CustomAnalysisModule(type=amt)
    manager.add_module(module)

    amt = AnalysisModuleType("test", "", extended_version=["intel:v2"])
    await system.register_analysis_module_type(amt)

    # this should fail since the upgrade fails
    assert not await manager.run()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_async_module_timeout(system):

    # define a module that times out immediately
    class TimeoutAsyncAnalysisModule(AsyncAnalysisModule):
        # define the type for this analysis module
        type = AnalysisModuleType("test", "")
        timeout = 0

        # define it as an async module
        async def execute_analysis(self, root, observable, analysis):
            await asyncio.sleep(1)  # should fail

    # create an instance of it
    module = TimeoutAsyncAnalysisModule()

    # register the type to the core
    await system.register_analysis_module_type(module.type)

    # submit a root for analysis so we create a new job
    root = system.new_root()
    observable = root.add_observable("test", "test")
    await root.submit()

    # create a new manager to run our analysis modules
    manager = AnalysisModuleManager(system)
    manager.add_module(module)
    await manager.run_once()

    # check the results in the core
    root = await system.get_root_analysis(root)
    observable = root.get_observable(observable)
    analysis = observable.get_analysis(module.type)
    assert analysis
    assert analysis.error_message == "testv1.0.0 timed out analyzing type test value test after 0 seconds"
