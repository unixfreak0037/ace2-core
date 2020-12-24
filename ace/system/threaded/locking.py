# vim: ts=4:sw=4:et:cc=120
#
# An implementation of the locking system using python threads.
#

import datetime
import logging
import threading

from typing import Union, Optional

from ace.system.locking import LockingInterface


class Lock:

    lock_id = None
    owner = None
    acquire_date = None
    expiration_date = None
    count = None

    """Base class that implements the actual lock being held.
    See TimeoutRLock below."""

    def acquire(self, owner, blocking=True, timeout=0, lock_timeout=None):
        raise NotImplementedError()

    def release(self, owner):
        raise NotImplementedError()

    def delete(self):
        raise NotImplementedError()

    def __str__(self):
        return (
            f"Lock({self.lock_id} owned by {self.owner} acquired {self.acquire_date} "
            f"expires {self.expiration_date} count {self.count}"
        )


class TimeoutRLock(Lock):
    """An implementation of an RLock that can timeout into an unlocked state."""

    def __init__(self, lock_id: str):
        # what is actually locked
        self.lock_id = lock_id
        # what everything waits for
        self.condition = threading.Condition()
        # what is used for the lock
        self.lock = threading.Lock()
        # re-entrant locking count
        self.count = 0
        # how many threads are waiting for this lock?
        self._wait_count = 0
        # who currently owns the lock
        self.owner = None
        # when the lock was acquired
        self.acquire_date = None
        # when the lock expires
        self.expiration_date = None
        # sync between threads (used for acquire and release)
        # in this case locking is a multi step process
        self.sync_lock = threading.Lock()

    @property
    def wait_count(self):
        with self.condition:
            return self._wait_count

    def acquire(self, *args, **kwargs):
        with self.sync_lock:
            return self.execute_acquire(*args, **kwargs)

    def execute_acquire(self, owner, blocking=True, timeout=0, lock_timeout=None):
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
                    self._wait_count += 1
                    self.condition.wait(wait_seconds)
                    self._wait_count -= 1

                    # NOTE that there's a step now between when the lock is released
                    # and when we pick it up
                    # so it's no longer first come first lock

                    # are we not able to grab it now?
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

        # we've acquired the lock at this point
        self.acquire_date = datetime.datetime.now()
        self.expiration_date = None

        # did we specify a lock timeout?
        if lock_timeout is not None:
            self.expiration_date = self.acquire_date + datetime.timedelta(seconds=lock_timeout)

            # if we specified 0 then we don't even need to wait, it just expires right away
            # this doesn't happen much in practice, more useful for testing lock expiration
            if lock_timeout == 0:
                self.expire()
                # but we still ended up locking it
                return True
            else:
                # start the clock
                self.start_timeout(lock_timeout)

        # assign the lock
        self.owner = owner
        # this is used to implement the reentrant functionality
        self.count = 1
        return True

    def release(self, *args, **kwargs):
        with self.sync_lock:
            return self.execute_release(*args, **kwargs)

    def execute_release(self, owner):
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

    def expire(self):
        """Expires the lock which resets it and notifies all others waiting for it."""
        logging.debug(f"lock id({self}) timeout expired")

        with self.condition:
            # reset the lock
            self.lock = threading.Lock()
            self.owner = None
            self.count = 0
            # self.acquire_date = None
            # self.expiration_date = None

            # and then notify that the lock is ready again
            self.condition.notify_all()

    def start_timeout(self, lock_timeout: float):
        self.timeout_monitor = threading.Thread(target=self.monitor_timeout)
        self.timeout_monitor.daemon = True
        self.timeout_monitor.start()

    def monitor_timeout(self):
        with self.condition:
            # wait until this many seconds have expired OR the lock is released
            lock_timeout = (self.expiration_date - datetime.datetime.now()).total_seconds()
            if lock_timeout < 0:
                lock_timeout = 0

            if not self.condition.wait(lock_timeout):
                # if the lock was not released then we make a new lock and notify everyone
                self.expire()

    def delete(self):
        pass


class ThreadedLockingInterface(LockingInterface):

    locks = {}  # key = lock_id, value = TimeoutRLock
    owner_wait_targets = {}  # key = owner_id, value = str (lock_id)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sync_lock = threading.RLock()

    def get_lock_count(self):
        with self.sync_lock:
            return len(self.locks)

    def get_lock_class(self) -> type:
        """Returns the class to use that extends the Lock class this interfaces uses to create locks."""
        return TimeoutRLock

    def get_lock_owner(self, lock_id: str) -> Union[str, None]:
        lock = self.locks.get(lock_id)
        if not lock:
            return None

        return lock.owner

    def get_owner_wait_target(self, owner_id: str) -> Union[str, None]:
        return self.owner_wait_targets.get(owner_id)

    def track_wait_target(self, lock_id: str, owner_id: str):
        self.owner_wait_targets[owner_id] = lock_id

    def clear_wait_target(self, owner_id: str):
        self.owner_wait_targets.pop(owner_id, None)

    def acquire(
        self, lock_id: str, owner_id: str, timeout: Optional[float] = None, lock_timeout: Optional[float] = None
    ) -> bool:

        with self.sync_lock:
            lock = self.locks.get(lock_id)
            if not lock:
                lock = self.create_lock(lock_id)

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

        result = lock.acquire(owner_id, arg_blocking, arg_timeout, lock_timeout)
        self.clear_expired_locks()
        return result

    def release(self, lock_id: str, owner_id: str) -> bool:
        with self.sync_lock:
            lock = self.locks.get(lock_id)

        if not lock:
            logging.debug(f"attempt to release unknown lock {lock_id} by {owner_id}")
            return False

        result = lock.release(owner_id)
        if result:
            # if this is no longer locked AND nothing else is waiting for it...
            if lock.count == 0 and lock.wait_count < 1:
                with self.sync_lock:
                    self.delete_lock(lock_id)
        else:
            logging.debug(f"failed to release {lock_id} by {owner_id}")

        # logging.debug(
        # f"{result} lock.release({lock_id}, {owner_id} lock = {id(lock)} cur_owner = {lock.owner} count = {lock.count}"
        # )
        return result

    def is_locked(self, lock_id: str) -> bool:
        lock = self.locks.get(lock_id, None)
        if not lock:
            return False

        return lock.count > 0

    def reset(self):
        self.locks = {}  # key = lock_id, value = threading.Lock
        self.owner_wait_targets = {}  # key = owner_id, value = str (lock_id)

    #
    # utility functions
    #

    def create_lock(self, lock_id: str) -> Lock:
        """Creates a lock with the given id and tracks it."""
        lock = self.get_lock_class()(lock_id)
        with self.sync_lock:
            self.locks[lock_id] = lock

        return lock

    def delete_lock(self, lock_id: str) -> bool:
        """Removes the lock with the given id from tracking."""
        with self.sync_lock:
            return self.locks.pop(lock_id, None) is not None

    def clear_expired_locks(self):
        """Removes any locks that have expired and have nothing waiting on them."""
        expired_lock_ids = []
        with self.sync_lock:
            for lock_id, lock in self.locks.items():
                with lock.sync_lock:
                    if lock.count == 0 and lock.wait_count < 1 and lock.expiration_date is not None:
                        expired_lock_ids.append(lock_id)

        for lock_id in expired_lock_ids:
            logging.debug(f"deleting expired lock {lock_id}")
            self.delete_lock(lock_id)
