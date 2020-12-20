# vim: ts=4:sw=4:et:cc=120

import datetime
import logging
import threading

from typing import Union, Optional

from ace.system.distributed import get_distributed_connection
from ace.system.locking import LockingInterface
from ace.system.threaded import ThreadedLockingInterface

import rpyc

# XXX
logging.getLogger("DISTRIBUTEDLOCKINGINTERFACE/12345").setLevel(logging.ERROR)


class DistributedLockingInterfaceService(ThreadedLockingInterface, rpyc.Service):
    def exposed_get_lock_owner(self, lock_id: str) -> Union[str, None]:
        return self.get_lock_owner(lock_id)

    def exposed_get_owner_wait_target(self, owner_id: str) -> Union[str, None]:
        return self.get_owner_wait_target(owner_id)

    def exposed_track_wait_target(self, lock_id: str, owner_id: str):
        self.track_wait_target(lock_id, owner_id)

    def exposed_track_lock_acquire(self, lock_id: str, owner_id: str, lock_timeout: Optional[int] = None):
        self.track_lock_acquire(lock_id, owner_id, lock_timeout)

    def exposed_acquire(
        self, lock_id: str, owner_id: str, timeout: Optional[int] = None, lock_timeout: Optional[int] = None
    ) -> bool:
        return self.acquire(lock_id, owner_id, timeout, lock_timeout)

    def exposed_release(self, lock_id: str, owner_id: str) -> bool:
        return self.release(lock_id, owner_id)

    def exposed_is_locked(self, lock_id: str) -> bool:
        return self.is_locked(lock_id)

    def exposed_reset(self):
        self.reset()


class DistributedLockingInterfaceClient(LockingInterface):
    def get_lock_owner(self, lock_id: str) -> Union[str, None]:
        with get_distributed_connection() as connection:
            return connection.root.get_lock_owner(lock_id)

    def get_owner_wait_target(self, owner_id: str) -> Union[str, None]:
        with get_distributed_connection() as connection:
            return connection.root.get_owner_wait_target(owner_id)

    def track_wait_target(self, lock_id: str, owner_id: str):
        with get_distributed_connection() as connection:
            connection.root.track_wait_target(lock_id, owner_id)

    def track_lock_acquire(self, lock_id: str, owner_id: str, lock_timeout: Optional[int] = None):
        with get_distributed_connection() as connection:
            connection.root.track_lock_acquire(lock_id, owner_id, lock_timeout)

    def acquire(
        self, lock_id: str, owner_id: str, timeout: Optional[int] = None, lock_timeout: Optional[int] = None
    ) -> bool:
        with get_distributed_connection() as connection:
            return connection.root.acquire(lock_id, owner_id, timeout, lock_timeout)

    def release(self, lock_id: str, owner_id: str) -> bool:
        with get_distributed_connection() as connection:
            return connection.root.release(lock_id, owner_id)

    def is_locked(self, lock_id: str) -> bool:
        with get_distributed_connection() as connection:
            return connection.root.is_locked(lock_id)

    def reset(self):
        with get_distributed_connection() as connection:
            connection.root.reset()
