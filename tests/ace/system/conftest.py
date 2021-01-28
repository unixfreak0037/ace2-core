import logging
import os
import os.path

import ace.system.distributed

from ace.system import ACESystem, get_system, set_system
from ace.system.database import DatabaseACESystem
from ace.system.distributed import DistributedACESystem
from ace.system.threaded import ThreadedACESystem
from ace.system.threaded.locking import ThreadedLockingInterface

import fastapi.testclient
import pytest


class ThreadedACETestSystem(ThreadedACESystem):
    pass


class DatabaseACETestSystem(DatabaseACESystem, ThreadedACESystem):

    # running this out of memory does not work due to the multithreading
    # each connection gets its own thread (thanks to session scoping)
    # and this in-memory db only exists for the connection its on
    # engine = create_engine("sqlite://")
    db_url = "sqlite:///ace.db"

    def reset(self):
        super().reset()

        # remove the temporary file we used
        if os.path.exists("ace.db"):
            os.remove("ace.db")

        # re-initialize and create the database
        self.initialize()
        self.create_database()

    def create_database(self):
        from ace.system.database import Base

        Base.metadata.bind = self.engine
        Base.metadata.create_all()

    def stop(self):
        super().stop()

        if os.path.exists("ace.db"):
            os.remove("ace.db")


class DistributedACETestSystem(DistributedACESystem, DatabaseACETestSystem, ThreadedACESystem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.locking.client = fastapi.testclient.TestClient(ace.system.distributed.locking.app)

    def initialize(self):
        super().initialize()
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
