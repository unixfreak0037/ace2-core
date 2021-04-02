# vim: ts=4:sw=4:et:cc=120

import json

from typing import Union, Optional

from ace.system.base import WorkQueueBaseInterface
from ace.system.requests import AnalysisRequest
from ace.exceptions import UnknownAnalysisModuleTypeError
from ace.time import utc_now

#
# we use two keys for each work queue due to the way redis works
# one key is used as a marker for when the queue exists
# the other contains the list of requests (the actual queue)
#

KEY_WORK_QUEUES = "work_queues"


def get_queue_name(name: str) -> str:
    return f"work_queue:{name}"


class RedisWorkQueueManagerInterface(WorkQueueBaseInterface):
    async def i_add_work_queue(self, name: str) -> bool:
        async with self.get_redis_connection() as rc:
            # this has to exist for the queue to exist
            return await rc.hsetnx(KEY_WORK_QUEUES, name, str(utc_now())) == 1

    async def i_delete_work_queue(self, name: str) -> bool:
        async with self.get_redis_connection() as rc:
            # this has to exist for the queue to exist
            result = await rc.hdel(KEY_WORK_QUEUES, name)
            # the actual queue may or may not exist
            await rc.delete(get_queue_name(name))

        return result == 1

    async def i_put_work(self, amt: str, analysis_request: AnalysisRequest):
        async with self.get_redis_connection() as rc:
            if not await rc.hexists(KEY_WORK_QUEUES, amt):
                raise UnknownAnalysisModuleTypeError()

            await rc.rpush(get_queue_name(amt), analysis_request.to_json())

    async def i_get_work(self, amt: str, timeout: float) -> Union[AnalysisRequest, None]:
        async with self.get_redis_connection() as rc:
            if not await rc.hexists(KEY_WORK_QUEUES, amt):
                raise UnknownAnalysisModuleTypeError()

            # if we're not looking to wait then we use LPOP
            # this always returns a single result
            if timeout == 0:
                result = await rc.lpop(get_queue_name(amt))
                if result is None:
                    return None

                return AnalysisRequest.from_json(result.decode(), system=self)

            else:
                # if we have a timeout when we use BLPOP
                result = await rc.blpop(get_queue_name(amt), timeout=timeout)
                if result is None:
                    return None

                # this can return a tuple of results (key, item1, item2, ...)
                _, result = result
                return AnalysisRequest.from_json(result.decode(), system=self)

    async def i_get_queue_size(self, amt: str) -> int:
        async with self.get_redis_connection() as rc:
            if not await rc.hexists(KEY_WORK_QUEUES, amt):
                raise UnknownAnalysisModuleTypeError()

            return await rc.llen(get_queue_name(amt))
