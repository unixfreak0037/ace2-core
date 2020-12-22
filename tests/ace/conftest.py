import logging

from ace.system import ACESystem, get_system, set_system

from ace.system.threaded.alerting import ThreadedAlertTrackingInterface
from ace.system.threaded.analysis_module import ThreadedAnalysisModuleTrackingInterface
from ace.system.threaded.analysis_request import ThreadedAnalysisRequestTrackingInterface
from ace.system.threaded.analysis_tracking import ThreadedAnalysisTrackingInterface
from ace.system.threaded.events import ThreadedEventInterafce
from ace.system.threaded.config import ThreadedConfigurationInterface
from ace.system.threaded.caching import ThreadedCachingInterface
from ace.system.threaded.locking import ThreadedLockingInterface
from ace.system.threaded.observables import ThreadedObservableInterface
from ace.system.threaded.storage import ThreadedStorageInterface
from ace.system.threaded.work_queue import ThreadedWorkQueueManagerInterface

from ace.system.distributed.locking import DistributedLockingInterfaceClient

import ace.system.threaded
import ace.system.database
import ace.system.distributed

import fastapi.testclient

import pytest


class DistributedACESystem(ACESystem):
    def __init__(self, *args, **kwargs):
        self.alerting = ThreadedAlertTrackingInterface()
        self.analysis_tracking = ThreadedAnalysisTrackingInterface()
        self.caching = ThreadedCachingInterface()
        self.config = ThreadedConfigurationInterface()
        self.events = ThreadedEventInterafce()
        self.locking = DistributedLockingInterfaceClient()
        self.module_tracking = ThreadedAnalysisModuleTrackingInterface()
        self.observable = ThreadedObservableInterface()
        self.request_tracking = ThreadedAnalysisRequestTrackingInterface()
        self.storage = ThreadedStorageInterface()
        self.work_queue = ThreadedWorkQueueManagerInterface()
        self.locking.client = fastapi.testclient.TestClient(ace.system.distributed.locking.app)
        ace.system.distributed.locking.distributed_interface = ThreadedLockingInterface()

    def start(self):
        pass

    def stop(self):
        pass


@pytest.fixture(
    autouse=True,
    scope="session",
    params=[
        # (ace.system.threaded.initialize, None),
        # (ace.system.database.initialize, None),
        # (ace.system.distributed.initialize, ace.system.distributed.cleanup),
        DistributedACESystem,
    ],
)
def initialize_ace_system(request):
    logging.getLogger().setLevel(logging.DEBUG)
    set_system(request.param())
    get_system().start()

    yield

    get_system().stop()


@pytest.fixture(autouse=True, scope="function")
def reset_ace_system():
    get_system().reset()
