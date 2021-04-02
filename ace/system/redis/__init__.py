# vim: ts=4:sw=4:et:cc=120

import contextlib

from ace.system import ACESystem

import aioredis

from ace.system.redis.alerting import RedisAlertTrackingInterface
from ace.system.redis.events import RedisEventInterface
from ace.system.redis.work_queue import RedisWorkQueueManagerInterface


CONFIG_REDIS_HOST = "/ace/core/redis/host"
CONFIG_REDIS_PORT = "/ace/core/redis/port"
CONFIG_REDIS_DB = "/ace/core/redis/db"
CONFIG_REDIS_POOL_SIZE = "/ace/core/redis/pool_size"


class RedisACESystem(RedisAlertTrackingInterface, RedisEventInterface, RedisWorkQueueManagerInterface, ACESystem):
    """A partial implementation of the ACE core implemented using Redis."""

    redis_connection_pool = None

    @contextlib.asynccontextmanager
    async def get_redis_connection(self):
        """Returns a redis connection to use."""
        connection = None
        try:
            connection = await self._get_redis_connection()
            yield connection
        finally:
            pass

    async def _get_redis_connection(self):
        host = await self.get_config_value(CONFIG_REDIS_HOST)
        port = await self.get_config_value(CONFIG_REDIS_PORT)
        db = await self.get_config_value(CONFIG_REDIS_DB, default=0)
        pool_size = await self.get_config_value(CONFIG_REDIS_DB, default=10)

        if self.redis_connection_pool is None:
            if host and port:
                connection_info = (host, port)
            else:
                connection_info = host

            if not connection_info:
                raise ValueError("missing redis connection settings")

            self.redis_connection_pool = await aioredis.create_redis_pool(connection_info)

        return self.redis_connection_pool
