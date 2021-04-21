# vim: ts=4:sw=4:et:cc=120
#

import asyncio
import os
import os.path
import tempfile
import shutil

import ace.analysis

from ace.analysis import RootAnalysis, Observable, AnalysisModuleType, Analysis
from ace.logging import get_logger
from ace.constants import EVENT_ANALYSIS_ROOT_COMPLETED
from ace.system.distributed import app
from ace.system.events import EventHandler, Event
from ace.module.base import AnalysisModule, MultiProcessAnalysisModule
from ace.module.manager import AnalysisModuleManager, CONCURRENCY_MODE_PROCESS, CONCURRENCY_MODE_THREADED
from tests.systems import RemoteACETestSystem

import pytest


@pytest.mark.asyncio
@pytest.mark.system
async def test_basic_analysis_async(manager):

    # basic analysis module
    class TestAsyncAnalysisModule(AnalysisModule):
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
    await manager.system.register_analysis_module_type(module.type)

    # submit a root for analysis so we create a new job
    root = manager.system.new_root()
    observable = root.add_observable("test", "test")
    await root.submit()

    manager.add_module(module)
    await manager.run_once()

    # check the results in the core
    root = await manager.system.get_root_analysis(root)
    observable = root.get_observable(observable)
    analysis = observable.get_analysis(module.type)
    assert analysis
    assert await analysis.get_details() == {"test": "test"}
    assert analysis.observables[0] == ace.analysis.Observable("test", "hello")


class TestMultiProcessAnalysisModule(AnalysisModule):
    __test__ = False

    # define the type for this analysis module
    type = AnalysisModuleType("test", "")

    # mark it as multi process
    is_multi_process: bool = False

    async def execute_analysis(self, root, observable, analysis):
        analysis.set_details({"test": "test"})
        analysis.add_observable("test", "hello")
        return True


@pytest.mark.asyncio
@pytest.mark.system
async def test_basic_analysis_sync(manager):

    # create an instance of it
    module = TestMultiProcessAnalysisModule()

    # register the type to the core
    await manager.system.register_analysis_module_type(module.type)

    # submit a root for analysis so we create a new job
    root = manager.system.new_root()
    observable = root.add_observable("test", "test")
    await root.submit()

    # create a new manager to run our analysis modules
    manager.add_module(module)
    await manager.run_once()

    # check the results in the core
    root = await manager.system.get_root_analysis(root)
    observable = root.get_observable(observable)
    analysis = observable.get_analysis(module.type)
    assert analysis
    assert await analysis.get_details() == {"test": "test"}
    assert analysis.observables[0] == ace.analysis.Observable("test", "hello")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_force_stop_stuck_async_task(manager):
    control = asyncio.Event()

    class CustomAnalysisModule(AnalysisModule):
        async def execute_analysis(self, root, observable, analysis):
            nonlocal control
            control.set()
            # get stuck
            import sys

            await asyncio.sleep(sys.maxsize)

    # register the type to the core
    amt = AnalysisModuleType("test", "")
    await manager.system.register_analysis_module_type(amt)

    module = CustomAnalysisModule(amt)
    manager.add_module(module)

    root = manager.system.new_root()
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


class StuckAnalysisModule(MultiProcessAnalysisModule):
    async def execute_analysis(self, root, observable, analysis):
        # get stuck
        import time, sys

        time.sleep(1000)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_force_stop_stuck_sync_task(manager):
    # there's nothing you can do when concurrency is threaded
    if manager.concurrency_mode == CONCURRENCY_MODE_THREADED:
        pytest.skip(f"cannot test in concurrency_mode {manager.concurrency_mode}")

    # register the type to the core
    amt = AnalysisModuleType("test", "")
    await manager.system.register_analysis_module_type(amt)

    module = StuckAnalysisModule(amt)
    manager.add_module(module)

    root = manager.system.new_root()
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
async def test_raised_exception_during_async_analysis(manager):
    class CustomAnalysisModule(AnalysisModule):
        async def execute_analysis(self, root, observable, analysis):
            raise RuntimeError("failure")

    amt = AnalysisModuleType("test", "")
    await manager.system.register_analysis_module_type(amt)

    module = CustomAnalysisModule(amt)
    manager.add_module(module)

    root = manager.system.new_root()
    observable = root.add_observable("test", "test")
    await root.submit()

    await manager.run_once()

    root = await manager.system.get_root_analysis(root)
    observable = root.get_observable(observable)
    analysis = observable.get_analysis(amt)

    assert analysis.error_message == "testv1.0.0 failed analyzing type test value test: failure"
    assert analysis.stack_trace


class FailingAnalysisModule(MultiProcessAnalysisModule):
    async def execute_analysis(self, root, observable, analysis):
        raise RuntimeError("failure")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_raised_exception_during_sync_analysis(manager):
    amt = AnalysisModuleType("test", "")
    await manager.system.register_analysis_module_type(amt)

    module = FailingAnalysisModule(amt)
    manager.add_module(module)

    root = manager.system.new_root()
    observable = root.add_observable("test", "test")
    await root.submit()

    await manager.run_once()

    root = await manager.system.get_root_analysis(root)
    observable = root.get_observable(observable)
    analysis = observable.get_analysis(amt)

    assert analysis.error_message == "testv1.0.0 failed analyzing type test value test: failure"
    assert analysis.stack_trace


class CrashingAnalysisModule(MultiProcessAnalysisModule):
    async def execute_analysis(self, root, observable, analysis):
        import os, signal

        if observable.value == "crash":
            os.kill(os.getpid(), signal.SIGKILL)
        else:
            analysis.set_details({"test": "test"})


class SimpleSyncAnalysisModule(MultiProcessAnalysisModule):
    async def execute_analysis(self, root, observable, analysis):
        analysis.set_details({"test": "test"})


@pytest.mark.asyncio
@pytest.mark.integration
async def test_crashing_sync_analysis_module(manager):

    if manager.concurrency_mode == CONCURRENCY_MODE_THREADED:
        pytest.skip(f"cannot test in concurrency_mode {manager.concurrency_mode}")

    sync = asyncio.Event()

    class CustomEventHandler(EventHandler):
        async def handle_event(self, event: Event):
            sync.set()

        async def handle_exception(self, event: str, exception: Exception):
            pass

    # TODO when events are distributed modify this to use that
    await app.state.system.register_event_handler(EVENT_ANALYSIS_ROOT_COMPLETED, CustomEventHandler())

    amt_crashing = AnalysisModuleType("crash_test", "")
    amt_ok = AnalysisModuleType("ok", "")
    await manager.system.register_analysis_module_type(amt_crashing)
    await manager.system.register_analysis_module_type(amt_ok)

    # this is only supported in CONCURRENCY_MODE_PROCESS
    crashing_module = CrashingAnalysisModule(amt_crashing)
    ok_module = SimpleSyncAnalysisModule(amt_ok)

    manager.add_module(crashing_module)
    manager.add_module(ok_module)

    root = manager.system.new_root()
    observable = root.add_observable("test", "crash")
    await root.submit()

    await manager.run_once()

    # wait for analysis to complete
    assert await sync.wait()

    root = await manager.system.get_root_analysis(root)
    observable = root.get_observable(observable)
    analysis = observable.get_analysis(amt_crashing)

    assert analysis.error_message == "crash_testv1.0.0 process crashed when analyzing type test value crash"
    assert analysis.stack_trace

    observable = root.get_observable(observable)
    analysis = observable.get_analysis(amt_ok)

    #
    # the behavior of what happens to the other analysis modules that happen to
    # be running in the same manager seems to be undefined, so there's really
    # no way to test for that
    #

    # assert (
    # analysis.error_message == "okv1.0.0 process crashed when analyzing type test value crash"
    # and analysis.stack_trace
    # ) or await analysis.get_details() == {"test": "test"}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_upgraded_version_analysis_module(manager):
    # cannot test this in process concurrency mode because it requires shared events
    if manager.concurrency_mode == CONCURRENCY_MODE_PROCESS:
        pytest.skip(f"cannot test in concurrency_mode {manager.concurrency_mode}")

    # NOTE for this one we don't need to test both sync and async because
    # this check comes before analysis module execution (same for both)
    step_1 = asyncio.Event()

    class CustomAnalysisModule(MultiProcessAnalysisModule):
        async def execute_analysis(self, root, observable, analysis):
            nonlocal step_1
            analysis.set_details({"version": self.type.version})
            if not step_1.is_set():
                step_1.set()
                return

    amt = AnalysisModuleType("test", "", version="1.0.0")
    await manager.system.register_analysis_module_type(amt)

    module = CustomAnalysisModule(type=amt)
    manager.add_module(module)

    root = manager.system.new_root()
    observable = root.add_observable("test", "test")
    await root.submit()

    root_2 = manager.system.new_root()
    observable_2 = root_2.add_observable("test", "test")

    async def _upgrade():
        nonlocal step_1
        nonlocal root_2
        await step_1.wait()
        updated_amt = AnalysisModuleType("test", "", version="1.0.1")
        await manager.system.register_analysis_module_type(updated_amt)
        await root_2.submit()

    upgrade_task = asyncio.create_task(_upgrade())
    await manager.run()
    await upgrade_task

    # in this case the version mismatch just causes the manger to exit
    root = await manager.system.get_root_analysis(root_2)
    observable = root.get_observable(observable)
    # so no analysis should be seen
    assert observable.get_analysis(amt) is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_upgraded_extended_version_async_analysis_module(manager):
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
        async def execute_analysis(self, root, observable, analysis):
            nonlocal step_1
            analysis.set_details({"extended_version": self.type.extended_version})
            if not step_1.is_set():
                step_1.set()
                return

            step_2.set()

        async def upgrade(self):
            self.type.extended_version = {"intel": "v2"}

    amt = AnalysisModuleType("test", "", extended_version={"intel": "v1"})
    await manager.system.register_analysis_module_type(amt)

    module = CustomAnalysisModule(type=amt)
    manager.add_module(module)

    root = manager.system.new_root()
    observable = root.add_observable("test", "test")
    await root.submit()

    root_2 = manager.system.new_root()
    observable_2 = root_2.add_observable("test", "test")

    async def _update_intel():
        nonlocal step_1
        nonlocal root_2
        await step_1.wait()
        # update the extended version data for this module type
        updated_amt = AnalysisModuleType("test", "", extended_version={"intel": "v2"})
        await manager.system.register_analysis_module_type(updated_amt)
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

    root = await manager.system.get_root_analysis(root_2)
    observable = root.get_observable(observable)
    assert (await observable.get_analysis(amt).get_details())["extended_version"] == {"intel": "v2"}


class UpgradableAnalysisModule(MultiProcessAnalysisModule):
    async def execute_analysis(self, root, observable, analysis):
        analysis.set_details({"extended_version": self.type.extended_version})

    async def upgrade(self):
        self.type.extended_version = {"intel": "v2"}


@pytest.mark.parametrize("concurrency_mode", [CONCURRENCY_MODE_THREADED, CONCURRENCY_MODE_PROCESS])
@pytest.mark.asyncio
@pytest.mark.integration
async def test_upgraded_extended_version_sync_analysis_module(concurrency_mode, redis_url, manager):
    """Tests the ability of a sync analysis module to update extended version data."""

    # we want to bail after the first execution of the module
    class CustomAnalysisModuleManager(AnalysisModuleManager):
        async def execute_module(self, *args, **kwargs):
            try:
                result = await AnalysisModuleManager.execute_module(self, *args, **kwargs)
            finally:
                self.shutdown = True

            return result

    custom_manager = CustomAnalysisModuleManager(
        manager.system, RemoteACETestSystem, (manager.system.api.api_key,), concurrency_mode=concurrency_mode
    )

    root_analysis_completed = asyncio.Event()

    class CustomEventHandler(EventHandler):
        async def handle_event(self, event: Event):
            root_analysis_completed.set()

        async def handle_exception(self, event: str, exception: Exception):
            pass

    # TODO when events are distributed modify this to use that
    await app.state.system.register_event_handler(EVENT_ANALYSIS_ROOT_COMPLETED, CustomEventHandler())

    amt = AnalysisModuleType("test", "", extended_version={"intel": "v1"})
    await custom_manager.system.register_analysis_module_type(amt)

    module = UpgradableAnalysisModule(type=amt)
    custom_manager.add_module(module)

    root = custom_manager.system.new_root()
    observable = root.add_observable("test", "test")

    async def _update_intel():
        nonlocal custom_manager
        # wait for the event loop to start
        await custom_manager.event_loop_starting_event.wait()
        # update the extended version data for this module type
        updated_amt = AnalysisModuleType("test", "", extended_version={"intel": "v2"})
        await custom_manager.system.register_analysis_module_type(updated_amt)
        # and then submit for analysis
        await root.submit()

    upgrade_task = asyncio.create_task(_update_intel())
    await custom_manager.run()
    await upgrade_task
    await root_analysis_completed.wait()

    root = await custom_manager.system.get_root_analysis(root)
    observable = root.get_observable(observable)
    assert (await observable.get_analysis(amt).get_details())["extended_version"] == {"intel": "v2"}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_upgrade_analysis_module_failure(manager):

    amt = AnalysisModuleType("test", "", extended_version={"intel": "v1"})
    await manager.system.register_analysis_module_type(amt)

    class CustomAnalysisModule(MultiProcessAnalysisModule):
        async def execute_analysis(self, *args, **kwargs):
            pass

        async def upgrade(self):
            raise RuntimeError()

    module = CustomAnalysisModule(type=amt)
    manager.add_module(module)

    amt = AnalysisModuleType("test", "", extended_version={"intel": "v2"})
    await manager.system.register_analysis_module_type(amt)

    # this should fail since the upgrade fails
    assert not await manager.run()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_async_module_timeout(manager):

    # define a module that times out immediately
    class TimeoutAsyncAnalysisModule(AnalysisModule):
        # define the type for this analysis module
        type = AnalysisModuleType("test", "")
        timeout = 0

        # define it as an async module
        async def execute_analysis(self, root, observable, analysis):
            await asyncio.sleep(1)  # should fail

    # create an instance of it
    module = TimeoutAsyncAnalysisModule()

    # register the type to the core
    await manager.system.register_analysis_module_type(module.type)

    # submit a root for analysis so we create a new job
    root = manager.system.new_root()
    observable = root.add_observable("test", "test")
    await root.submit()

    # create a new manager to run our analysis modules
    manager.add_module(module)
    await manager.run_once()

    # check the results in the core
    root = await manager.system.get_root_analysis(root)
    observable = root.get_observable(observable)
    analysis = observable.get_analysis(module.type)
    assert analysis
    assert analysis.error_message == "testv1.0.0 timed out analyzing type test value test after 0 seconds"


class FileAnalysisModule(AnalysisModule):
    type = AnalysisModuleType("test", "")

    async def execute_analysis(self, root, observable, analysis):
        tmpdir = tempfile.mkdtemp()
        target_path = os.path.join(tmpdir, "test.txt")
        with open(target_path, "w") as fp:
            fp.write("test")

        await analysis.add_file(target_path)
        shutil.rmtree(tmpdir)


class MultiProcessFileAnalysisModule(FileAnalysisModule):
    is_multi_process = True


@pytest.mark.parametrize("module_class", [FileAnalysisModule, MultiProcessFileAnalysisModule])
@pytest.mark.asyncio
@pytest.mark.integration
async def test_module_add_file(manager, tmpdir, module_class):
    # adding file content is treated specially by the core since it has to upload and download the content

    # create an instance of it
    module = module_class()

    # register the type to the core
    await manager.system.register_analysis_module_type(module.type)

    # submit a root for analysis so we create a new job
    root = manager.system.new_root()
    observable = root.add_observable("test", "test")
    await root.submit()

    # create a new manager to run our analysis modules
    manager.add_module(module)
    await manager.run_once()

    # check the results in the core
    root = await manager.system.get_root_analysis(root)
    observable = root.get_observable(observable)
    analysis = observable.get_analysis(module.type)
    assert analysis
    file_observable = analysis.get_observable_by_type("file")
    assert file_observable

    meta = await manager.system.get_content_meta(file_observable.value)
    assert meta.name == "test.txt"
    assert meta.sha256 == file_observable.value

    content = await manager.system.get_content_bytes(file_observable.value)
    assert content.decode() == "test"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_analyze_file_observable(manager, tmpdir):

    # basic analysis module
    class TestFileAnalysisModule(AnalysisModule):
        # define the type for this analysis module
        type = AnalysisModuleType("test", "", ["file"])

        # define it as an async module
        async def execute_analysis(self, root, observable, analysis):
            analysis.set_details({"result": os.path.exists(observable.path)})
            return True

    # create an instance of it
    module = TestFileAnalysisModule()

    # register the type to the core
    await manager.system.register_analysis_module_type(module.type)

    target_file = str(tmpdir / "test.txt")
    with open(target_file, "w") as fp:
        fp.write("test")

    # submit the file ahead of time
    sha256 = await manager.system.save_file(target_file)

    # delete our copy of it
    os.remove(target_file)

    root = manager.system.new_root()
    observable = root.add_observable("file", sha256)
    await root.submit()

    manager.add_module(module)
    await manager.run_once()

    # check the results in the core
    root = await manager.system.get_root_analysis(root)
    observable = root.get_observable(observable)
    analysis = observable.get_analysis(module.type)
    assert analysis
    details = await analysis.get_details()
    assert details["result"] is True

    #
    # when the requested file content is unavailable the analysis is not requested
    #

    root = manager.system.new_root()
    observable = root.add_observable("file", sha256)
    await root.submit()

    await app.state.system.delete_content(sha256)

    manager.add_module(module)
    await manager.run_once()

    # check the results in the core
    root = await manager.system.get_root_analysis(root)
    observable = root.get_observable(observable)
    analysis = observable.get_analysis(module.type)
    assert analysis
    assert analysis.error_message == "unknown file"
