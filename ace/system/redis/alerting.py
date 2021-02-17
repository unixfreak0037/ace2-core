# vim: ts=4:sw=4:et:cc=120
#

#
# NOTE the timeout option for get_alerts has to be an int for Redis < version 6
# so we're using integers for now

from typing import Optional

from ace.system.alerting import AlertTrackingInterface, UnknownAlertSystem
from ace.system.redis import get_redis_connection
from ace.time import utc_now

KEY_ALERT_SYSTEMS = "alert_systems"


def get_alert_queue(name: str) -> str:
    return f"alert_system:{name}"


class RedisAlertTrackingInterface(AlertTrackingInterface):

    redis_connection = get_redis_connection

    def register_alert_system(self, name: str) -> bool:
        with self.redis_connection() as rc:
            return rc.hsetnx(KEY_ALERT_SYSTEMS, name, str(utc_now())) == 1

    def unregister_alert_system(self, name: str) -> bool:
        with self.redis_connection() as rc:
            return rc.hdel(KEY_ALERT_SYSTEMS, name) == 1

    def submit_alert(self, root_uuid: str) -> bool:
        with self.redis_connection() as rc:
            result = False
            for name in rc.hkeys(KEY_ALERT_SYSTEMS):
                result = True
                name = name.decode()
                rc.rpush(get_alert_queue(name), root_uuid)

        return result

    def get_alerts(self, name: str, timeout: Optional[int] = None) -> list[str]:
        with self.redis_connection() as rc:
            if not rc.hexists(KEY_ALERT_SYSTEMS, name):
                raise UnknownAlertSystem(name)

            result = []

            if timeout is None:
                while True:
                    alert_uuid = rc.lpop(get_alert_queue(name))
                    if alert_uuid is None:
                        break

                    result.append(alert_uuid.decode())

                return result

            else:
                # if a timeout is specified then only a single alert is returned
                # if we have a timeout when we use BLPOP
                result = rc.blpop(get_alert_queue(name), timeout=timeout)
                if result is None:
                    return []

                # this returns a tuple of results (key, item1)
                _, result = result
                return [result.decode()]

    def get_alert_count(self, name: str) -> int:
        with self.redis_connection() as rc:
            if not rc.hexists(KEY_ALERT_SYSTEMS, name):
                raise UnknownAlertSystem(name)

            return rc.llen(get_alert_queue(name))
