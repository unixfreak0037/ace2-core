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
from ace.crypto import initialize_encryption_settings, EncryptionSettings
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
    db_url = "sqlite+aiosqlite://"

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
        await self.create_database()

        # reset the storage_root
        shutil.rmtree(self.storage_root)
        self.storage_root = tempfile.mkdtemp()

    async def create_database(self):
        from ace.system.database.schema import Base

        get_logger().info(f"creating database {self.db_url}")
        Base.metadata.bind = self.engine
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Base.metadata.create_all()

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
        await self.close_redis_connections()
        # async with self.get_redis_connection() as rc:
        # rc.close()
        # await rc.wait_closed()


class DistributedACETestSystem(RedisACETestSystem):
    db_url = "sqlite+aiosqlite:///ace_distributed.db"

    async def reset(self):
        if os.path.exists("ace_distributed.db"):
            os.remove("ace_distributed.db")

        await super().reset()


class RemoteACETestSystem(RemoteACESystem):
    def __init__(self, api_key: str):
        super().__init__("http://test", api_key, client_args=[], client_kwargs={"app": app})


class RemoteACETestSystemProcess(RemoteACESystem):
    def __init__(self, redis_url: str, api_key: str, encryption_settings: EncryptionSettings, *args, **kwargs):
        super().__init__("http://test", None, client_args=[], client_kwargs={"app": app}, *args, **kwargs)
        self.redis_url = redis_url
        self.api.api_key = api_key
        self.existing_encryption_settings = encryption_settings

    async def initialize(self):
        await super().initialize()

        print("*** initializing app.state.system ***")

        # configure the distributed system that sits behind the fake FastAPI
        app.state.system = DistributedACETestSystem()
        from ace.system.redis import CONFIG_REDIS_HOST, CONFIG_REDIS_PORT

        # pull the unix path from the redislist connection pool
        await app.state.system.set_config(CONFIG_REDIS_HOST, self.redis_url)

        #
        # NOTE app.state.system is actually already set up by RemoteACETestSystem
        # so all we need to do is to use the existing settings passed in on the constructor
        #

        app.state.system.encryption_settings = self.existing_encryption_settings
        app.state.system.encryption_settings.load_aes_key("test")
        app.state.system.root_api_key = self.api.api_key

        await app.state.system.initialize()

        print("*** app.state.system initialized OK ***")
