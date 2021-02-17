import logging
import os
import os.path

import ace.system.distributed

from ace.system import ACESystem, get_system, set_system, get_logger
from ace.system.database import DatabaseACESystem, CONFIG_DB_URL, CONFIG_DB_KWARGS
from ace.system.distributed import DistributedACESystem
from ace.system.threaded import ThreadedACESystem

import fastapi.testclient
import pytest


class ThreadedACETestSystem(ThreadedACESystem):
    pass


class DatabaseACETestSystem(DatabaseACESystem, ThreadedACESystem):

    # running this out of memory does not work due to the multithreading
    # each connection gets its own thread (thanks to session scoping)
    # and this in-memory db only exists for the connection its on
    # engine = create_engine("sqlite://")
    # db_url = "sqlite:///ace.db"
    db_url = "sqlite://"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def reset(self):
        super().reset()

        self.db = None

        # remove the temporary file we used
        # if os.path.exists("ace.db"):
        # os.remove("ace.db")

        # re-initialize and create the database
        self.initialize()
        self.create_database()

    def create_database(self):
        from ace.system.database import Base

        Base.metadata.bind = self.engine
        Base.metadata.create_all()

    def stop(self):
        super().stop()

        # if os.path.exists("ace.db"):
        # os.remove("ace.db")


class DistributedACETestSystem(DistributedACESystem, DatabaseACETestSystem, ThreadedACESystem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.redis_connection = None

    def initialize(self):
        super().initialize()

        # if os.path.exists("ace.rdb"):
        # os.remove("ace.rdb")

        # only need to do this once
        if self.redis_connection is None:
            import redislite

            self.redis_connection = redislite.StrictRedis("ace.rdb")
            self.alerting.redis_connection = lambda: self.redis_connection
            self.work_queue.redis_connection = lambda: self.redis_connection
            self.events.redis_connection = lambda: self.redis_connection

    def reset(self):
        super().reset()

        # clear everything
        get_logger().debug("clearing redis...")
        self.redis_connection.flushall()


@pytest.fixture(
    autouse=True,
    scope="session",
    params=[
        # ThreadedACETestSystem,
        DatabaseACETestSystem,
        DistributedACETestSystem,
    ],
)
def initialize_ace_system(request):
    get_logger().setLevel(logging.DEBUG)
    # logging.getLogger().setLevel(logging.DEBUG)
    set_system(request.param())
    get_system().initialize()
    get_system().start()

    yield

    get_system().stop()


@pytest.fixture(autouse=True, scope="function")
def reset_ace_system():
    get_system().reset()
