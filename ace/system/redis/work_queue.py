# vim: ts=4:sw=4:et:cc=120

CONFIG_REDIS_HOST = "/ace/core/redis/host"
CONFIG_REDIS_PORT = "/ace/core/redis/port"
CONFIG_REDIS_DB = "/ace/core/redis/db"

import json

from typing import Union, Optional

from ace.system import ACESystemInterface
from ace.system.analysis_module import UnknownAnalysisModuleTypeError
from ace.system.analysis_request import AnalysisRequest
from ace.system.work_queue import WorkQueueManagerInterface
from ace.time import utc_now

import redis

#
# we use two keys for each work queue due to the way redis works
# one key is used as a marker for when the queue exists
# the other contains the list of requests (the actual queue)
#


def get_marker_name(name: str) -> str:
    return f"work_queue_marker:{name}"


def get_queue_name(name: str) -> str:
    return f"work_queue:{name}"


def get_redis_connection():
    """Returns a redis connection to use."""
    return redis.Redis(
        host=get_config(CONFIG_REDIS_HOST, default="localhost"),
        port=get_config(CONFIG_REDIS_PORT, default=6379),
        db=get_config(CONFIG_REDIS_DB, default=0),
    )


class RedisWorkQueueManagerInterface(WorkQueueManagerInterface):

    redis_connection = get_redis_connection

    def delete_work_queue(self, name: str) -> bool:
        with self.redis_connection() as rc:
            # this has to exist for the queue to exist
            result = rc.delete(get_marker_name(name))
            # the actual queue may or may not exist
            rc.delete(get_queue_name(name))

        return result == 1

    def add_work_queue(self, name: str) -> bool:
        with self.redis_connection() as rc:
            # this has to exist for the queue to exist
            return rc.setnx(get_marker_name(name), str(utc_now())) == 1
            # NOTE we don't add the actual queue because you can't add an empty list

    def put_work(self, amt: str, analysis_request: AnalysisRequest):
        with self.redis_connection() as rc:
            if not rc.exists(get_marker_name(amt)):
                raise UnknownAnalysisModuleTypeError(amt)

            rc.rpush(get_queue_name(amt), analysis_request.to_json())

    def get_work(self, amt: str, timeout: float) -> Union[AnalysisRequest, None]:
        with self.redis_connection() as rc:
            if not rc.exists(get_marker_name(amt)):
                raise UnknownAnalysisModuleTypeError(amt)

            # if we're not looking to wait then we use LPOP
            # this always returns a single result
            if timeout == 0:
                result = rc.lpop(get_queue_name(amt))
                if result is None:
                    return None

                return AnalysisRequest.from_json(result.decode())

            else:
                # if we have a timeout when we use BLPOP
                result = rc.blpop(get_queue_name(amt), timeout=timeout)
                if result is None:
                    return None

                # this can return a tuple of results (key, item1, item2, ...)
                _, result = result
                return AnalysisRequest.from_json(result.decode())

    def get_queue_size(self, amt: str) -> int:
        with self.redis_connection() as rc:
            if not rc.exists(get_marker_name(amt)):
                raise UnknownAnalysisModuleTypeError(amt)

            return rc.llen(get_queue_name(amt))
