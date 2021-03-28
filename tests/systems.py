# vim: ts=4:sw=4:et:cc=120
#

#
# utility system definitions for testing
#

import os
import os.path
import tempfile
import shutil

from ace.api import AceAPI
from ace.api.remote import RemoteAceAPI
from ace.system.database import DatabaseACESystem
from ace.system.distributed import app
from ace.system.redis import RedisACESystem
from ace.system.remote import RemoteACESystem
from ace.system.threaded import ThreadedACESystem

from httpx import AsyncClient
import redislite


class ThreadedACETestSystem(ThreadedACESystem):
    pass


class DatabaseACETestSystem(DatabaseACESystem, ThreadedACESystem):

    # running the tests in memory works as long as the same db connection is
    # always used

    # db_url = "sqlite:///ace.db"
    db_url = "sqlite://"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.storage_root = tempfile.mkdtemp()

    async def reset(self):
        result = await super().reset()

        self.engine = None

        # remove the temporary file we used
        if os.path.exists("ace.db"):
            os.remove("ace.db")

        # re-initialize and create the database
        await self.initialize()
        self.create_database()

        # reset the storage_root
        shutil.rmtree(self.storage_root)
        self.storage_root = tempfile.mkdtemp()

    def create_database(self):
        from ace.system.database.schema import Base

        Base.metadata.bind = self.engine
        Base.metadata.create_all()

    def stop(self):
        super().stop()

        if os.path.exists("ace.db"):
            os.remove("ace.db")


class RedisACETestSystem(RedisACESystem, DatabaseACETestSystem, ThreadedACESystem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._redis_connection = None

    def get_redis_connection(self):
        """Returns a redis connection to use."""
        if self._redis_connection is None:
            self._redis_connection = redislite.StrictRedis("ace.rdb")
            # self._redis_connection.flushall()

        return self._redis_connection

    async def reset(self):
        await super().reset()

        # clear everything
        with self.get_redis_connection() as rc:
            self._redis_connection.flushall()


class DistributedACETestSystem(RedisACETestSystem):
    db_url = "sqlite:///ace.db"

    def get_redis_connection(self):
        """Returns a redis connection to use."""
        if self._redis_connection is None:
            self._redis_connection = redislite.StrictRedis("ace.rdb")

        return self._redis_connection

    async def initialize(self):
        # add the initial super-user api key
        await super().initialize()


class RemoteACETestSystem(RemoteACESystem, RedisACETestSystem):
    db_url = "sqlite:///ace.db"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api = RemoteAceAPI(self)
        self.api.client_args = []
        self.api.client_kwargs = {
            "app": app,
            "base_url": "http://test",
        }

    def get_api(self):
        return self.api
