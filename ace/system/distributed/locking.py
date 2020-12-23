# vim: ts=4:sw=4:et:cc=120

import datetime
import logging
import threading

from typing import Union, Optional

from ace.system import get_system
from ace.system.locking import LockingInterface
from ace.system.threaded.locking import ThreadedLockingInterface

from fastapi import FastAPI
import requests

app = FastAPI()
distributed_interface = None


@app.get("/get_lock_owner/{lock_id}")
def get_lock_owner(lock_id: str):
    return {"result": distributed_interface.get_lock_owner(lock_id)}


@app.get("/get_owner_wait_target/{owner_id}")
def get_owner_wait_target(owner_id: str):
    return {"result": distributed_interface.get_owner_wait_target(owner_id)}


@app.put("/track_wait_target/{lock_id}/{owner_id}")
def track_wait_target(lock_id: str, owner_id: str):
    distributed_interface.track_wait_target(lock_id, owner_id)


@app.put("/clear_wait_target/{owner_id}")
def clear_wait_target(owner_id: str):
    distributed_interface.clear_wait_target(owner_id)


@app.put("/track_lock_acquire/{lock_id}/{owner_id}")
def track_lock_acquire(lock_id: str, owner_id: str, lock_timeout: Optional[float] = None):
    return {"result": distributed_interface.track_lock_acquire(lock_id, owner_id, lock_timeout)}


@app.get("/acquire/{lock_id}/{owner_id}")
def acquire(lock_id: str, owner_id: str, timeout: Optional[float] = None, lock_timeout: Optional[float] = None):
    return {"result": distributed_interface.acquire(lock_id, owner_id, timeout, lock_timeout)}


@app.put("/release/{lock_id}/{owner_id}")
def release(lock_id: str, owner_id: str):
    return {"result": distributed_interface.release(lock_id, owner_id)}


@app.get("/is_locked/{lock_id}")
def is_locked(lock_id: str):
    return {"result": distributed_interface.is_locked(lock_id)}


@app.get("/get_lock_count")
def get_lock_count():
    return {"result": distributed_interface.get_lock_count()}


@app.post("/reset")
def reset():
    return distributed_interface.reset()


@app.on_event("startup")
def startup_event():
    global distributed_threading
    distributed_threading = ThreadedLockingInterface()


class DistributedLockingInterfaceClient(LockingInterface):

    client = requests

    def get_lock_owner(self, lock_id: str) -> Union[str, None]:
        result = self.client.get(f"/get_lock_owner/{lock_id}")
        result.raise_for_status()
        return result.json()["result"]

    def get_owner_wait_target(self, owner_id: str) -> Union[str, None]:
        result = self.client.get(f"/get_owner_wait_target/{owner_id}")
        result.raise_for_status()
        return result.json()["result"]

    def track_wait_target(self, lock_id: str, owner_id: str):
        result = self.client.put(f"/track_wait_target/{lock_id}/{owner_id}")
        result.raise_for_status()

    def clear_wait_target(self, owner_id):
        result = self.client.put(f"/clear_wait_target/{owner_id}")
        result.raise_for_status

    def track_lock_acquire(self, lock_id: str, owner_id: str, lock_timeout: Optional[float] = None):
        params = None
        if lock_timeout is not None:
            params = {"lock_timeout": lock_timeout}

        result = self.client.put(f"/track_lock_acquire/{lock_id}/{owner_id}", params=params)
        result.raise_for_status()

    def acquire(
        self, lock_id: str, owner_id: str, timeout: Optional[float] = None, lock_timeout: Optional[float] = None
    ) -> bool:
        params = {}
        if timeout is not None:
            params["timeout"] = timeout
        if lock_timeout is not None:
            params["lock_timeout"] = lock_timeout

        result = self.client.get(f"/acquire/{lock_id}/{owner_id}", params=params)
        result.raise_for_status()
        return result.json()["result"]

    def release(self, lock_id: str, owner_id: str) -> bool:
        result = self.client.put(f"/release/{lock_id}/{owner_id}")
        result.raise_for_status()
        return result.json()["result"]

    def is_locked(self, lock_id: str) -> bool:
        result = self.client.get(f"/is_locked/{lock_id}")
        result.raise_for_status()
        return result.json()["result"]

    def get_lock_count(self) -> int:
        result = self.client.get(f"/get_lock_count")
        result.raise_for_status()
        return result.json()["result"]

    def reset(self):
        result = self.client.post(f"/reset")
        result.raise_for_status()
