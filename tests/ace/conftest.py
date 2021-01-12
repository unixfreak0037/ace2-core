import logging
import os
import os.path

import ace.system.distributed

from ace.system import ACESystem, get_system, set_system
from ace.system.config import set_config
from ace.system.database import DatabaseACESystem
from ace.system.database.analysis_module import DatabaseAnalysisModuleTrackingInterface
from ace.system.database.analysis_request import DatabaseAnalysisRequestTrackingInterface
from ace.system.database.analysis_tracking import DatabaseAnalysisTrackingInterface
from ace.system.database.caching import DatabaseCachingInterface
from ace.system.database.locking import DatabaseLockingInterface
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
from ace.system.redis.work_queue import RedisWorkQueueManagerInterface

import fastapi.testclient
import pytest


class ThreadedACETestSystem(ACESystem):
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


class DatabaseACETestSystem(DatabaseACESystem):
    alerting = ThreadedAlertTrackingInterface()
    analysis_tracking = DatabaseAnalysisTrackingInterface()
    caching = DatabaseCachingInterface()
    config = ThreadedConfigurationInterface()
    events = ThreadedEventInterafce()
    locking = DatabaseLockingInterface()
    module_tracking = DatabaseAnalysisModuleTrackingInterface()
    observable = DatabaseObservableInterface()
    request_tracking = DatabaseAnalysisRequestTrackingInterface()
    storage = ThreadedStorageInterface()
    work_queue = ThreadedWorkQueueManagerInterface()

    def reset(self):
        super().reset()

        # remove the temporary file we used
        if os.path.exists("ace.db"):
            os.remove("ace.db")

        # re-initialize and create the database
        self.initialize()
        self.create_database()

    def initialize(self):
        # running this out of memory does not work due to the multithreading
        # each connection gets its own thread (thanks to session scoping)
        # and this in-memory db only exists for the connection its on
        # engine = create_engine("sqlite://")

        set_config("/ace/core/sqlalchemy/url", "sqlite:///ace.db")
        super().initialize()

    def stop(self):
        super().stop()

        if os.path.exists("ace.db"):
            os.remove("ace.db")


class DistributedACETestSystem(ACESystem):
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
    work_queue = RedisWorkQueueManagerInterface()
    locking.client = fastapi.testclient.TestClient(ace.system.distributed.locking.app)

    def initialize(self):
        import fakeredis

        rc = fakeredis.FakeStrictRedis()
        self.work_queue.redis_connection = lambda: rc

    def reset(self):
        super().reset()

        import fakeredis

        rc = fakeredis.FakeStrictRedis()
        self.work_queue.redis_connection = lambda: rc


ace.system.distributed.locking.distributed_interface = ThreadedLockingInterface()


@pytest.fixture(
    autouse=True,
    scope="session",
    params=[
        ThreadedACETestSystem,
        DatabaseACETestSystem,
        DistributedACETestSystem,
    ],
)
def initialize_ace_system(request):
    logging.getLogger().setLevel(logging.DEBUG)
    set_system(request.param())
    get_system().initialize()
    get_system().start()

    yield

    get_system().stop()


@pytest.fixture(autouse=True, scope="function")
def reset_ace_system():
    get_system().reset()
