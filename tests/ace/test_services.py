# vim: sw=4:ts=4:et:cc=120

import asyncio
import os.path
import signal

import pytest

from ace.constants import SERVICE_STATUS_RUNNING, SERVICE_STATUS_UNKNOWN, SERVICE_STATUS_STOPPED
from ace.service.base import ACEService
from ace.service.manager import ACEServiceManager


@pytest.fixture(scope="function")
def manager(tmpdir):
    db_path = str(tmpdir + "service.db")
    # when the manager starts it changes the signal handlers for INT and TERM
    # so we change them back when we're done
    orig_int = signal.getsignal(signal.SIGINT)
    orig_term = signal.getsignal(signal.SIGTERM)
    yield ACEServiceManager(db_path)
    signal.signal(signal.SIGINT, orig_int)
    signal.signal(signal.SIGTERM, orig_term)


class TestService(ACEService):
    __test__ = False
    name = "test_service"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service_executed = asyncio.Event()

    async def run(self):
        """Main execution routine of the service. Must be overridden. Does not return until service stops."""
        self.service_executed.set()
        await self.shutdown_event.wait()


class TestManagedService(ACEService):
    __test__ = False
    name = "test_service"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service_executed = asyncio.Event()

    async def run(self):
        """Main execution routine of the service. Must be overridden. Does not return until service stops."""
        self.service_executed.set()


class TestManagedServiceSignals(ACEService):
    __test__ = False
    name = "test_managed_service"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def run(self):
        """Main execution routine of the service. Must be overridden. Does not return until service stops."""
        self.sig_HUP = asyncio.Event()
        self.sig_USR1 = asyncio.Event()
        self.sig_USR2 = asyncio.Event()

        os.kill(os.getpid(), signal.SIGHUP)
        os.kill(os.getpid(), signal.SIGUSR1)
        os.kill(os.getpid(), signal.SIGUSR2)

        await self.sig_HUP.wait()
        await self.sig_USR1.wait()
        await self.sig_USR2.wait()

    def signal_handler_HUP(self):
        self.sig_HUP.set()

    def signal_handler_USR1(self):
        self.sig_USR1.set()

    def signal_handler_USR2(self):
        self.sig_USR2.set()


class TestManagedBackgroundService(ACEService):
    __test__ = False
    name = "test_background_service"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service_started_event = multiprocessing.Event()

    async def run(self):
        self.service_started_event.set()
        await self.shutdown_event.wait()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_start_stop_service():
    service = TestService()
    # start the service
    task = asyncio.get_event_loop().create_task(service.start())
    # wait for it to start
    await service.service_executed.wait()
    # tell it to stop
    await service.stop()
    # wait for it to stop
    await task
    # ensure it actually ran
    assert service.service_executed.is_set()


@pytest.mark.unit
def test_manager_set_get_service_status():
    pass


@pytest.mark.integration
def test_managed_service_start_stop(manager):
    service = TestManagedService()
    assert manager.get_service_status(service.name) == SERVICE_STATUS_UNKNOWN
    manager.schedule_service(service)
    assert manager.get_service_status(service.name) == SERVICE_STATUS_STOPPED
    manager.start()  # blocking call

    assert service.service_executed.is_set()
    assert manager.get_service_status(service.name) == SERVICE_STATUS_STOPPED


@pytest.mark.integration
def test_managed_service_signals(manager):
    service = TestManagedServiceSignals()
    manager.schedule_service(service)
    manager.start()  # blocking call

    assert service.sig_HUP.is_set()
    assert service.sig_USR1.is_set()
    assert service.sig_USR2.is_set()


@pytest.mark.unit
def test_initialize_service_db(manager):
    assert os.path.exists(manager.db.db_path)


@pytest.mark.unit
def test_set_get_service_info(manager):
    assert manager.db.get_service_info("test") is None
    manager.db.set_service_info("test", SERVICE_STATUS_RUNNING, 1)
    info = manager.db.get_service_info("test")
    assert info.name == "test"
    assert info.status == SERVICE_STATUS_RUNNING
    assert info.pid == 1
    manager.db.set_service_info("test", SERVICE_STATUS_STOPPED)
    info = manager.db.get_service_info("test")
    assert info.name == "test"
    assert info.status == SERVICE_STATUS_STOPPED
    assert info.pid is None
    manager.db.delete_service("test")
    assert manager.db.get_service_info("test") is None


@pytest.mark.unit
def test_schedule_service(manager):
    service = TestService()
    manager.schedule_service(service)
    assert service.name in manager.services
