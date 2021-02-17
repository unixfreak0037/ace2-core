# vim: ts=4:sw=4:et:cc=120
#

import fastapi.testclient

from ace.system.redis.alerting import RedisAlertTrackingInterface
from ace.system.redis.events import RedisEventInterface
from ace.system.redis.work_queue import RedisWorkQueueManagerInterface


class DistributedACESystem:
    """A partial implementation of the ACE core implemented using various distributed systems."""

    alerting = RedisAlertTrackingInterface()
    events = RedisEventInterface()
    work_queue = RedisWorkQueueManagerInterface()
