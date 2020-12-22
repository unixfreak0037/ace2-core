import logging

import ace.database

from ace.system import ACESystem, get_system, set_system
from ace.system.database.analysis_module import DatabaseAnalysisModuleTrackingInterface
from ace.system.database.analysis_request import DatabaseAnalysisRequestTrackingInterface
from ace.system.database.analysis_tracking import DatabaseAnalysisTrackingInterface
from ace.system.database.caching import DatabaseCachingInterface
from ace.system.database.observables import DatabaseObservableInterface
from ace.system.distributed.locking import DistributedLockingInterfaceClient
from ace.system.threaded.alerting import ThreadedAlertTrackingInterface
from ace.system.threaded.analysis_module import ThreadedAnalysisModuleTrackingInterface
from ace.system.threaded.analysis_request import ThreadedAnalysisRequestTrackingInterface
from ace.system.threaded.analysis_tracking import ThreadedAnalysisTrackingInterface
from ace.system.threaded.caching import ThreadedCachingInterface
from ace.system.threaded.config import ThreadedConfigurationInterface
from ace.system.threaded.events import ThreadedEventInterafce
from ace.system.threaded.locking import ThreadedLockingInterface
from ace.system.threaded.observables import ThreadedObservableInterface
from ace.system.threaded.storage import ThreadedStorageInterface
from ace.system.threaded.work_queue import ThreadedWorkQueueManagerInterface

import fastapi.testclient
import pytest

class ThreadedACESystem(ACESystem):
    work_queue = ThreadedWorkQueueManagerInterface()
    request_tracking = ThreadedAnalysisRequestTrackingInterface()
    module_tracking = ThreadedAnalysisModuleTrackingInterface()
    analysis_tracking = ThreadedAnalysisTrackingInterface()
    caching = ThreadedCachingInterface()
    storage = ThreadedStorageInterface()
    locking = ThreadedLockingInterface()
    observable = ThreadedObservableInterface()
    config = ThreadedConfigurationInterface()
    alerting = ThreadedAlertTrackingInterface()
    events = ThreadedEventInterafce()

class DatabaseACESystem(ACESystem):
    alerting = ThreadedAlertTrackingInterface()
    analysis_tracking = DatabaseAnalysisTrackingInterface()
    caching = DatabaseCachingInterface()
    config = ThreadedConfigurationInterface()
    events = ThreadedEventInterafce()
    locking = ThreadedLockingInterface()
    module_tracking = DatabaseAnalysisModuleTrackingInterface()
    observable = DatabaseObservableInterface()
    request_tracking = DatabaseAnalysisRequestTrackingInterface()
    storage = ThreadedStorageInterface()
    work_queue = ThreadedWorkQueueManagerInterface()

    def _rebuild_database(self):
        ace.database.initialize_database()
        ace.database.Base.metadata.bind = ace.database.engine
        ace.database.Base.metadata.create_all()

    def start(self):
        self._rebuild_database()

    def reset(self):
        super().reset()
        self._rebuild_database()

class DistributedACESystem(ACESystem):
    alerting = ThreadedAlertTrackingInterface()
    analysis_tracking = ThreadedAnalysisTrackingInterface()
    caching = ThreadedCachingInterface()
    config = ThreadedConfigurationInterface()
    events = ThreadedEventInterafce()
    locking = DistributedLockingInterfaceClient()
    module_tracking = ThreadedAnalysisModuleTrackingInterface()
    observable = ThreadedObservableInterface()
    request_tracking = ThreadedAnalysisRequestTrackingInterface()
    storage = ThreadedStorageInterface()
    work_queue = ThreadedWorkQueueManagerInterface()
    locking.client = fastapi.testclient.TestClient(ace.system.distributed.locking.app)

ace.system.distributed.locking.distributed_interface = ThreadedLockingInterface()

@pytest.fixture(
    autouse=True,
    scope="session",
    params=[
        ThreadedACESystem,
        DatabaseACESystem,
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
