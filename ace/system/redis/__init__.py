# vim: ts=4:sw=4:et:cc=120

import contextlib

from ace.system import ACESystem

import redis

from ace.system.redis.alerting import RedisAlertTrackingInterface
from ace.system.redis.events import RedisEventInterface
from ace.system.redis.work_queue import RedisWorkQueueManagerInterface


CONFIG_REDIS_HOST = "/ace/core/redis/host"
CONFIG_REDIS_PORT = "/ace/core/redis/port"
CONFIG_REDIS_DB = "/ace/core/redis/db"


class RedisACESystem(RedisAlertTrackingInterface, RedisEventInterface, RedisWorkQueueManagerInterface, ACESystem):
    """A partial implementation of the ACE core implemented using Redis."""

    @contextlib.asynccontextmanager
    async def get_redis_connection(self):
        """Returns a redis connection to use."""
        connection = None
        try:
            connection = await self._get_redis_connection()
            yield connection
        finally:
            if connection:
                connection.close()

    async def _get_redis_connection(self):
        return redis.Redis(
            host=await self.get_config_value(CONFIG_REDIS_HOST, default="localhost"),
            port=await self.get_config_value(CONFIG_REDIS_PORT, default=6379),
            db=await self.get_config_value(CONFIG_REDIS_DB, default=0),
        )
