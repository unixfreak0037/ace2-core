# vim: ts=4:sw=4:et:cc=120

# vim: sw=4:ts=4:et:cc=120

import datetime
import logging
import threading

from functools import wraps
from typing import Union, Optional

import ace
from ace.database.schema import Lock as DBLock, LockOwnerWaitTarget
from ace.system.threaded.locking import ThreadedLockingInterface, TimeoutRLock, Lock
from ace.system.locking import LockingInterface


class DatabaseTimeoutRLock(TimeoutRLock):
    def execute_acquire(self, owner, blocking=True, timeout=0, lock_timeout=None):
        result = super().execute_acquire(owner, blocking, timeout, lock_timeout)
        self._update_db()
        return result

    def execute_release(self, owner):
        result = super().execute_release(owner)
        self._update_db()
        return result

    def _update_db(self):
        ace.db.merge(
            DBLock(
                id=self.lock_id,
                owner=self.owner,
                acquire_date=self.acquire_date,
                expiration_date=self.expiration_date,
                count=self.count,
            )
        )
        ace.db.commit()


class DatabaseLockingInterface(ThreadedLockingInterface):
    def get_lock_class(self) -> type:
        return DatabaseTimeoutRLock

    def track_wait_target(self, lock_id: str, owner_id: str):
        super().track_wait_target(lock_id, owner_id)
        wait_target = LockOwnerWaitTarget(owner=owner_id, lock_id=lock_id)
        ace.db.merge(wait_target)
        ace.db.commit()

    def clear_wait_target(self, owner_id: str):
        super().clear_wait_target(owner_id)
        ace.db.execute(LockOwnerWaitTarget.__table__.delete().where(LockOwnerWaitTarget.owner == owner_id))
        ace.db.commit()
