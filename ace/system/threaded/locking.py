# vim: ts=4:sw=4:et:cc=120

import datetime
import logging
import threading

from functools import wraps
from typing import Union, Optional

from ace.system.threaded import ThreadedInterface
from ace.system.locking import LockingInterface


class TimeoutRLock:
    """An implementation of an RLock that can timeout into an unlocked state."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # what everything waits for
        self.condition = threading.Condition()
        # what is used for the lock
        self.lock = threading.Lock()
        # re-entrant locking count
        self.count = 0
        # who currently owns the lock
        self.owner = None

        self.sync_lock = threading.Lock()

    def acquire(self, *args, **kwargs):
        with self.sync_lock:
            return self._acquire(*args, **kwargs)

    def _acquire(self, owner, blocking=True, timeout=0, lock_timeout=None):
        if self.owner == owner:
            # XXX restart the clock
            self.count += 1
            return True

        wait_timeout = None
        if blocking:
            # the time this request will expire if the lock is not granted
            wait_timeout = datetime.datetime.now() + datetime.timedelta(seconds=timeout)

        while True:
            with self.condition:
                # are we not able to grab it right away?
                if not self.lock.acquire(blocking=False):
                    if not blocking:
                        # if we're not blocking then we're already done
                        return False

                    # how long do we have left to wait?
                    wait_seconds = (wait_timeout - datetime.datetime.now()).total_seconds()
                    if wait_seconds < 0:
                        wait_seconds = 0

                    # wait for that long or until the lock is released
                    self.condition.wait(wait_seconds)

                    # are we able to grab it now?
                    if not self.lock.acquire(blocking=False):
                        # has our request expired yet?
                        if datetime.datetime.now() >= wait_timeout:
                            return False
                    else:
                        # able to lock it after waiting
                        break
                else:
                    # able to lock it right away
                    break

        # lock has been acquired, did we specify a lock timeout?
        if lock_timeout is not None:
            # if we specified 0 then we don't even need to wait, it just expires right away
            if lock_timeout == 0:
                with self.condition:
                    logging.debug(f"lock id({self}) timeout expired")
                    self.lock = threading.Lock()
                    self.owner = None
                    self.count = 0
                    self.condition.notify_all()
                    return True  # but we still locked it
            else:
                self.start_timeout(lock_timeout)

        self.owner = owner
        self.count = 1
        return True

    def start_timeout(self, lock_timeout: float):
        logging.debug(f"starting lock id({self}) timeout for {lock_timeout} seconds")
        # XXX should this be a daemon thread?
        self.timeout_monitor = threading.Thread(target=self.monitor_timeout, args=(lock_timeout,))
        self.timeout_monitor.start()

    def monitor_timeout(self, lock_timeout: float):
        with self.condition:
            # wait until this many seconds have expired OR the lock is released
            # XXX use short times to check for changes
            if not self.condition.wait(lock_timeout):
                logging.debug(f"lock id({self}) timeout expired")
                # if the lock was not released then we make a new lock and notify everyone
                self.lock = threading.Lock()
                self.owner = None
                self.count = 0
                self.condition.notify_all()

    def release(self, *args, **kwargs):
        with self.sync_lock:
            return self._release(*args, **kwargs)

    def _release(self, owner):
        if self.owner != owner:
            logging.debug(f"failed to release lock {self} ({self.lock}): invalid owner")
            return False

        self.count -= 1
        if self.count:
            return True

        self.owner = None

        try:
            self.lock.release()
        except RuntimeError as e:
            # if we attempt to release after expire then this will fail because
            # we'll either not own it or it will not be locked yet
            # because the locks were switched out
            logging.debug(f"failed to release lock {id(self)} req owner {owner} cur owner {self.owner}: {e}")
            return False

        with self.condition:
            self.condition.notify_all()

        return True


def synchronized(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        with self.sync_lock:
            return func(self, *args, **kwargs)

    return wrapper


class ThreadedLockingInterface(ThreadedInterface, LockingInterface):

    locks = {}  # key = lock_id, value = threading.Lock
    lock_ownership = {}  # key = lock_id, value = str (owner_id)
    owner_wait_targets = {}  # key = owner_id, value = str (lock_id)
    lock_timeouts = {}  # key = lock_id, value = datetime.datetime when lock expires
    current_locks = set()  # key = lock_id

    def get_lock_owner(self, lock_id: str) -> Union[str, None]:
        return self.lock_ownership.get(lock_id)

    def get_owner_wait_target(self, owner_id: str) -> Union[str, None]:
        return self.owner_wait_targets.get(owner_id)

    def track_wait_target(self, lock_id: str, owner_id: str):
        self.owner_wait_targets[owner_id] = lock_id

    def track_lock_acquire(self, lock_id: str, owner_id: str, lock_timeout: Optional[float] = None):
        self.lock_ownership[lock_id] = owner_id
        if lock_timeout:
            lock_timeout = datetime.datetime.now() + datetime.timedelta(seconds=lock_timeout)
        self.lock_timeouts[lock_id] = lock_timeout

    def acquire(
        self, lock_id: str, owner_id: str, timeout: Optional[float] = None, lock_timeout: Optional[float] = None
    ) -> bool:
        lock = self.locks.get(lock_id)
        if not lock:
            lock = self.locks[lock_id] = TimeoutRLock()

        arg_blocking = True
        arg_timeout = -1

        if timeout is None:
            arg_blocking = True
            arg_timeout = -1
        elif timeout == 0:
            arg_blocking = False
            arg_timeout = -1
        else:
            arg_blocking = True
            arg_timeout = timeout

        success = lock.acquire(owner_id, arg_blocking, arg_timeout, lock_timeout)
        if success:
            # if we were able to lock it keep track of that so we can implement is_locked()
            # XXX
            self.current_locks.add(lock_id)

        # logging.debug(f"{success} lock.acquire({lock_id}, {owner_id}, {timeout}, {lock_timeout} lock = {id(lock)} cur owner = {lock.owner} count = {lock.count}")
        return success

    def release(self, lock_id: str, owner_id: str) -> bool:
        lock = self.locks.get(lock_id)
        if not lock:
            logging.debug(f"attempt to release unknown lock {lock_id} by {owner_id}")
            return False

        result = lock.release(owner_id)
        if result:
            if lock.count == 0:
                self.current_locks.remove(lock_id)
        else:
            logging.debug(f"failed to release {lock_id} by {owner_id}")

        # logging.debug(f"{result} lock.release({lock_id}, {owner_id} lock = {id(lock)} cur_owner = {lock.owner} count = {lock.count}")
        return result

    def is_locked(self, lock_id: str) -> bool:
        return lock_id in self.current_locks

    def reset(self):
        self.locks = {}  # key = lock_id, value = threading.Lock
        self.lock_ownership = {}  # key = lock_id, value = str (owner_id)
        self.owner_wait_targets = {}  # key = owner_id, value = str (lock_id)
