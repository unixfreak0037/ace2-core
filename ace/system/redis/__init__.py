# vim: ts=4:sw=4:et:cc=120

from ace.system import ACESystem

import redis

CONFIG_REDIS_HOST = "/ace/core/redis/host"
CONFIG_REDIS_PORT = "/ace/core/redis/port"
CONFIG_REDIS_DB = "/ace/core/redis/db"


from ace.system.redis.alerting import RedisAlertTrackingInterface
from ace.system.redis.events import RedisEventInterface
from ace.system.redis.work_queue import RedisWorkQueueManagerInterface


class RedisACESystem(RedisAlertTrackingInterface, RedisEventInterface, RedisWorkQueueManagerInterface, ACESystem):
    """A partial implementation of the ACE core implemented using Redis."""

    def get_redis_connection(self):
        """Returns a redis connection to use."""
        return redis.Redis(
            host=self.config.get_config_value(CONFIG_REDIS_HOST, default="localhost"),
            port=self.config.get_config_value(CONFIG_REDIS_PORT, default=6379),
            db=self.config.get_config_value(CONFIG_REDIS_DB, default=0),
        )
