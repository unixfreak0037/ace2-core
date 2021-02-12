# vim: ts=4:sw=4:et:cc=120

from ace.system.config import get_config

import redis

CONFIG_REDIS_HOST = "/ace/core/redis/host"
CONFIG_REDIS_PORT = "/ace/core/redis/port"
CONFIG_REDIS_DB = "/ace/core/redis/db"


def get_redis_connection():
    """Returns a redis connection to use."""
    return redis.Redis(
        host=get_config(CONFIG_REDIS_HOST, default="localhost"),
        port=get_config(CONFIG_REDIS_PORT, default=6379),
        db=get_config(CONFIG_REDIS_DB, default=0),
    )
