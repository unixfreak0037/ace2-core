# vim: ts=4:sw=4:et:cc=120
#

#
# XXX this in particular is going to be super confusing
# we're using ace.system.analysis and ace.api.analysis in the same code here
#

import asyncio

import ace.analysis
import ace.api.analysis

from ace.analysis import RootAnalysis, Observable
from ace.system.analysis_tracking import get_root_analysis
from ace.system.analysis_module import register_analysis_module_type
from ace.api.analysis import AnalysisModuleType, Analysis
from ace.module.base import AnalysisModule
from ace.module.manager import AnalysisModuleManager, CONCURRENCY_MODE_PROCESS, CONCURRENCY_MODE_THREADED

import pytest


@pytest.mark.system
@pytest.mark.asyncio
async def test_basic_analysis_async():

    # basic analysis module
    class TestAsyncAnalysisModule(AnalysisModule):
        # define the type for this analysis module
        type = ace.api.analysis.AnalysisModuleType("test", "")

        # define it as an async module
        async def execute_analysis(
            self, root: ace.api.analysis.RootAnalysis, observable: ace.api.analysis.Observable
        ) -> bool:
            analysis = observable.add_analysis(ace.api.analysis.Analysis(type=self.type, details={"test": "test"}))
            analysis.add_observable("test", "hello")
            return True

    # create an instance of it
    module = TestAsyncAnalysisModule()

    # register the type to the core
    register_analysis_module_type(module.type)

    # submit a root for analysis so we create a new job
    root = ace.analysis.RootAnalysis()
    observable = root.add_observable("test", "test")
    root.submit()

    # create a new manager to run our analysis modules
    manager = AnalysisModuleManager()
    manager.add_module(module)
    await manager.run_once()

    # check the results in the core
    root = get_root_analysis(root)
    observable = root.get_observable(observable)
    analysis = observable.get_analysis(module.type)
    assert analysis
    assert analysis.details == {"test": "test"}
    assert analysis.observables[0] == ace.analysis.Observable("test", "hello")


class TestSyncAnalysisModule(AnalysisModule):
    __test__ = False

    # define the type for this analysis module
    type = ace.api.analysis.AnalysisModuleType("test", "")

    # define it as an sync module
    def execute_analysis(self, root: ace.api.analysis.RootAnalysis, observable: ace.api.analysis.Observable) -> bool:
        analysis = observable.add_analysis(ace.api.analysis.Analysis(type=self.type, details={"test": "test"}))
        analysis.add_observable("test", "hello")
        return True


@pytest.mark.parametrize("concurrency_mode", [CONCURRENCY_MODE_THREADED, CONCURRENCY_MODE_PROCESS])
@pytest.mark.system
@pytest.mark.asyncio
async def test_basic_analysis_sync(concurrency_mode):

    # create an instance of it
    module = TestSyncAnalysisModule()

    # register the type to the core
    register_analysis_module_type(module.type)

    # submit a root for analysis so we create a new job
    root = ace.analysis.RootAnalysis()
    observable = root.add_observable("test", "test")
    root.submit()

    # create a new manager to run our analysis modules
    manager = AnalysisModuleManager(concurrency_mode=concurrency_mode)
    manager.add_module(module)
    await manager.run_once()

    # check the results in the core
    root = get_root_analysis(root)
    observable = root.get_observable(observable)
    analysis = observable.get_analysis(module.type)
    assert analysis
    assert analysis.details == {"test": "test"}
    assert analysis.observables[0] == ace.analysis.Observable("test", "hello")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_force_stop_stuck_async_task():
    control = asyncio.Event()

    class CustomAnalysisModule(AnalysisModule):
        async def execute_analysis(self, root, observable):
            nonlocal control
            control.set()
            # get stuck
            import sys

            await asyncio.sleep(sys.maxsize)

    # register the type to the core
    amt = ace.api.analysis.AnalysisModuleType("test", "")
    register_analysis_module_type(amt)

    manager = AnalysisModuleManager()
    module = CustomAnalysisModule(amt)
    manager.add_module(module)

    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    root.submit()

    async def _cancel():
        nonlocal control
        nonlocal manager
        await control.wait()
        manager.force_stop()

    cancel_task = asyncio.get_event_loop().create_task(_cancel())
    await manager.run()
    await cancel_task


class StuckAnalysisModule(AnalysisModule):
    def execute_analysis(self, root, observable):
        # get stuck
        import time, sys

        time.sleep(1000)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_force_stop_stuck_sync_task():
    # register the type to the core
    amt = ace.api.analysis.AnalysisModuleType("test", "")
    register_analysis_module_type(amt)

    manager = AnalysisModuleManager(concurrency_mode=CONCURRENCY_MODE_PROCESS)
    module = StuckAnalysisModule(amt)
    manager.add_module(module)

    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    root.submit()

    async def _cancel():
        nonlocal manager
        manager.force_stop()

    manager_task = asyncio.get_event_loop().create_task(manager.run())
    await asyncio.wait([manager_task], timeout=0.01)
    cancel_task = asyncio.get_event_loop().create_task(_cancel())
    await manager_task
    await cancel_task


@pytest.mark.integration
@pytest.mark.asyncio
async def test_raised_exception_during_async_analysis():
    class CustomAnalysisModule(AnalysisModule):
        async def execute_analysis(self, root, observable):
            raise RuntimeError("failure")

    amt = ace.api.analysis.AnalysisModuleType("test", "")
    register_analysis_module_type(amt)

    manager = AnalysisModuleManager()
    module = CustomAnalysisModule(amt)
    manager.add_module(module)

    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    root.submit()

    await manager.run_once()

    root = get_root_analysis(root)
    observable = root.get_observable(observable)
    analysis = observable.get_analysis(amt)

    assert analysis.error_message == "RuntimeError: failure"
    assert analysis.stack_trace


class FailingAnalysisModule(AnalysisModule):
    def execute_analysis(self, root, observable):
        raise RuntimeError("failure")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_raised_exception_during_sync_analysis():
    amt = ace.api.analysis.AnalysisModuleType("test", "")
    register_analysis_module_type(amt)

    manager = AnalysisModuleManager()
    module = FailingAnalysisModule(amt)
    manager.add_module(module)

    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    root.submit()

    await manager.run_once()

    root = get_root_analysis(root)
    observable = root.get_observable(observable)
    analysis = observable.get_analysis(amt)

    assert analysis.error_message == "RuntimeError: failure"
    assert analysis.stack_trace


class CrashingAnalysisModule(AnalysisModule):
    def execute_analysis(self, root, observable):
        import os, signal

        os.kill(os.getpid(), signal.SIGKILL)


class SimpleSyncAnalysisModule(AnalysisModule):
    def execute_analysis(self, root, observable):
        observable.add_analysis(Analysis(type=self.type, details={"test": "test"}))


@pytest.mark.integration
@pytest.mark.asyncio
async def test_crashing_sync_analysis_module():
    amt_crashing = ace.api.analysis.AnalysisModuleType("crash_test", "")
    amt_ok = ace.api.analysis.AnalysisModuleType("ok", "")
    register_analysis_module_type(amt_crashing)
    register_analysis_module_type(amt_ok)

    # this is only supported in CONCURRENCY_MODE_PROCESS
    manager = AnalysisModuleManager(concurrency_mode=CONCURRENCY_MODE_PROCESS)
    crashing_module = CrashingAnalysisModule(amt_crashing)
    ok_module = SimpleSyncAnalysisModule(amt_ok)

    manager.add_module(crashing_module)
    manager.add_module(ok_module)

    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    root.submit()

    await manager.run_once()

    root = get_root_analysis(root)
    observable = root.get_observable(observable)
    analysis = observable.get_analysis(amt_crashing)

    assert analysis.error_message == "crash_test process crashed when analyzing test test"
    assert analysis.stack_trace

    observable = root.get_observable(observable)
    analysis = observable.get_analysis(amt_ok)

    assert analysis.error_message == "ok process crashed when analyzing test test"
    assert analysis.stack_trace


@pytest.mark.integration
@pytest.mark.asyncio
async def test_upgraded_version_analysis_module():
    # NOTE for this one we don't need to test both sync and async because
    # this check comes before analysis module execution (same for both)
    step_1 = asyncio.Event()

    class CustomAnalysisModule(AnalysisModule):
        def execute_analysis(self, root, observable):
            nonlocal step_1
            observable.add_analysis(Analysis(type=self.type, details={"version": self.type.version}))
            if not step_1.is_set():
                step_1.set()
                return

    amt = ace.api.analysis.AnalysisModuleType("test", "", version="1.0.0")
    register_analysis_module_type(amt)

    manager = AnalysisModuleManager()
    module = CustomAnalysisModule(type=amt)
    manager.add_module(module)

    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    root.submit()

    root_2 = RootAnalysis()
    observable_2 = root_2.add_observable("test", "test")

    async def _upgrade():
        nonlocal step_1
        nonlocal root_2
        await step_1.wait()
        updated_amt = ace.api.analysis.AnalysisModuleType("test", "", version="1.0.1")
        register_analysis_module_type(updated_amt)
        root_2.submit()

    upgrade_task = asyncio.create_task(_upgrade())
    await manager.run()
    await upgrade_task

    # in this case the version mismatch just causes the manger to exit
    root = get_root_analysis(root_2)
    observable = root.get_observable(observable)
    # so no analysis should be seen
    assert observable.get_analysis(amt) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_upgraded_extended_version_async_analysis_module():
    """Tests the ability of an analysis module to update extended version data."""

    #
    # in this case the first call to get_next_analysis_request fails
    # but the module.upgrade() is called
    # since the work task is not acquired it stays in the queue
    # until the event_loop comes back around with the correct extended version data
    #

    step_1 = asyncio.Event()
    step_2 = asyncio.Event()

    class CustomAnalysisModule(AnalysisModule):
        def execute_analysis(self, root, observable):
            nonlocal step_1
            observable.add_analysis(
                Analysis(type=self.type, details={"additional_cache_keys": self.type.additional_cache_keys})
            )
            if not step_1.is_set():
                step_1.set()
                return

            step_2.set()

        def upgrade(self):
            self.type.additional_cache_keys = ["intel:v2"]

    amt = ace.api.analysis.AnalysisModuleType("test", "", additional_cache_keys=["intel:v1"])
    register_analysis_module_type(amt)

    manager = AnalysisModuleManager()
    module = CustomAnalysisModule(type=amt)
    manager.add_module(module)

    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    root.submit()

    root_2 = RootAnalysis()
    observable_2 = root_2.add_observable("test", "test")

    async def _update_intel():
        nonlocal step_1
        nonlocal root_2
        await step_1.wait()
        # update the extended version data for this module type
        updated_amt = ace.api.analysis.AnalysisModuleType("test", "", additional_cache_keys=["intel:v2"])
        register_analysis_module_type(updated_amt)
        root_2.submit()

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

    root = get_root_analysis(root_2)
    observable = root.get_observable(observable)
    assert observable.get_analysis(amt).details["additional_cache_keys"] == ["intel:v2"]


class UpgradableAnalysisModule(AnalysisModule):
    def execute_analysis(self, root, observable):
        observable.add_analysis(
            Analysis(type=self.type, details={"additional_cache_keys": self.type.additional_cache_keys})
        )

    def upgrade(self):
        self.type.additional_cache_keys = ["intel:v2"]


@pytest.mark.parametrize("concurrency_mode", [CONCURRENCY_MODE_THREADED, CONCURRENCY_MODE_PROCESS])
@pytest.mark.integration
@pytest.mark.asyncio
async def test_upgraded_extended_version_sync_analysis_module(concurrency_mode):
    """Tests the ability of a sync analysis module to update extended version data."""

    amt = AnalysisModuleType("test", "", additional_cache_keys=["intel:v1"])
    register_analysis_module_type(amt)

    # we want to bail after the first execution of the module
    class CustomAnalysisModuleManager(AnalysisModuleManager):
        async def execute_module(self, *args, **kwargs):
            try:
                result = await AnalysisModuleManager.execute_module(self, *args, **kwargs)
            finally:
                self.shutdown = True

            return result

    manager = CustomAnalysisModuleManager(concurrency_mode=concurrency_mode)
    module = UpgradableAnalysisModule(type=amt)
    manager.add_module(module)

    root = RootAnalysis()
    observable = root.add_observable("test", "test")

    async def _update_intel():
        nonlocal manager
        # wait for the event loop to start
        await manager.event_loop_starting_event.wait()
        # update the extended version data for this module type
        updated_amt = AnalysisModuleType("test", "", additional_cache_keys=["intel:v2"])
        register_analysis_module_type(updated_amt)
        # and then submit for analysis
        root.submit()

    upgrade_task = asyncio.create_task(_update_intel())
    await manager.run()
    await upgrade_task

    root = get_root_analysis(root)
    observable = root.get_observable(observable)
    assert observable.get_analysis(amt).details["additional_cache_keys"] == ["intel:v2"]
