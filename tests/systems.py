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
from ace.logging import get_logger
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

        get_logger().info(f"creating database {self.db_url}")
        Base.metadata.bind = self.engine
        Base.metadata.create_all()

    async def stop(self):
        await super().stop()

        if os.path.exists("ace.db"):
            os.remove("ace.db")


class RedisACETestSystem(RedisACESystem, DatabaseACETestSystem, ThreadedACESystem):
    async def reset(self):
        await super().reset()

        # clear everything
        async with self.get_redis_connection() as rc:
            await rc.flushall()

    async def stop(self):
        async with self.get_redis_connection() as rc:
            rc.close()
            await rc.wait_closed()


class DistributedACETestSystem(RedisACETestSystem):
    db_url = "sqlite:///ace_distributed.db"

    async def reset(self):
        if os.path.exists("ace_distributed.db"):
            os.remove("ace_distributed.db")

        await super().reset()


class RemoteACETestSystem(RemoteACESystem, ThreadedACESystem):
    def __init__(self, *args, **kwargs):
        super().__init__("http://test", None, client_args=[], client_kwargs={"app": app}, *args, **kwargs)
        # self.api = RemoteAceAPI(self)
        # self.api.client_args = []
        # self.api.client_kwargs = {
        # "app": app,
        # "base_url": "http://test",
        # }

    # def get_api(self):
    # return self.api
