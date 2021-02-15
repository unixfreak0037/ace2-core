# vim: ts=4:sw=4:et:cc=120

from ace.system.config import get_config_value

import redis

CONFIG_REDIS_HOST = "/ace/core/redis/host"
CONFIG_REDIS_PORT = "/ace/core/redis/port"
CONFIG_REDIS_DB = "/ace/core/redis/db"


def get_redis_connection():
    """Returns a redis connection to use."""
    return redis.Redis(
        host=get_config_value(CONFIG_REDIS_HOST, default="localhost"),
        port=get_config_value(CONFIG_REDIS_PORT, default=6379),
        db=get_config_value(CONFIG_REDIS_DB, default=0),
    )


from ace.system.redis.events import RedisEventInterface
from ace.system.redis.work_queue import RedisWorkQueueManagerInterface


class RedisACESystem:
    """A partial implementation of the ACE core implemented using Redis."""

    events = RedisEventInterface()
    work_queue = RedisWorkQueueManagerInterface()
