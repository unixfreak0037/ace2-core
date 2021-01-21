# vim: ts=4:sw=4:et:cc=120
#

import fastapi.testclient

from ace.system.distributed.locking import DistributedLockingInterfaceClient
from ace.system.redis.work_queue import RedisWorkQueueManagerInterface


class DistributedACESystem:
    """A partial implementation of the ACE core implemented using various distributed systems."""

    locking = DistributedLockingInterfaceClient()
    work_queue = RedisWorkQueueManagerInterface()
