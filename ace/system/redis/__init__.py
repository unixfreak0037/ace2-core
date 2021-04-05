# vim: ts=4:sw=4:et:cc=120

import contextlib
import os
import threading

from ace.logging import get_logger
from ace.system import ACESystem

import aioredis

from ace.system.redis.alerting import RedisAlertTrackingInterface
from ace.system.redis.events import RedisEventInterface
from ace.system.redis.work_queue import RedisWorkQueueManagerInterface


CONFIG_REDIS_HOST = "/ace/core/redis/host"
CONFIG_REDIS_PORT = "/ace/core/redis/port"
CONFIG_REDIS_DB = "/ace/core/redis/db"
CONFIG_REDIS_POOL_SIZE = "/ace/core/redis/pool_size"


def _pool_key():
    return "{}:{}".format(os.getpid(), threading.get_ident())


class RedisACESystem(RedisAlertTrackingInterface, RedisEventInterface, RedisWorkQueueManagerInterface, ACESystem):
    """A partial implementation of the ACE core implemented using Redis."""

    pools = {}  # key = _pool_key(), value = aioredis.create_redis_pool

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
        # if the pid or tid change then we create a new pool
        pool_key = _pool_key()
        if pool_key not in self.pools:
            host = await self.get_config_value(CONFIG_REDIS_HOST)
            port = await self.get_config_value(CONFIG_REDIS_PORT)
            db = await self.get_config_value(CONFIG_REDIS_DB, default=0)
            pool_size = await self.get_config_value(CONFIG_REDIS_DB, default=100)

            if host and port:
                connection_info = (host, port)
            else:
                connection_info = host

            if not connection_info:
                raise ValueError("missing redis connection settings")

            get_logger().info(f"connecting to redis {connection_info} ({pool_key})")
            self.pools[pool_key] = await aioredis.create_redis_pool(connection_info)
            get_logger().debug(f"connected to redis {connection_info} ({pool_key})")

        return self.pools[pool_key]

    async def close_redis_connections(self):
        pool_key = _pool_key()
        get_logger().info(f"closing connection pool to redis ({pool_key})")
        if pool_key in self.pools:
            self.pools[pool_key].close()
            await self.pools[pool_key].wait_closed()
            del self.pools[pool_key]
