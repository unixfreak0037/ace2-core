# vim: sw=4:ts=4:et:cc=120

import asyncio
import os
import os.path
import signal
import sqlite3

from dataclasses import dataclass
from typing import Optional

from ace.constants import *
from ace.env import get_base_dir
from ace.exceptions import (
    UnknownServiceError,
    InvalidServiceStateError,
    ServiceAlreadyRunningError,
    ServiceDisabledError,
)
from ace.logging import get_logger
from ace.service.base import ACEService

import psutil

SERVICE_DB_SCHEMA = """
CREATE TABLE services (
    name TEXT UNIQUE,
    status TEXT,
    pid INT)
"""


@dataclass
class ServiceInfo:
    name: str
    status: str
    pid: int


class ACEServiceDB:
    def __init__(self, db_path: Optional[str] = None):
        """Initializes the service database at the given path.
        Defaults to get_base_dir()/services.db"""

        self.db_path = db_path
        if self.db_path is None:
            self.db_path = os.path.join(get_base_dir(), "services.db")

        if not os.path.isdir(os.path.dirname(self.db_path)):
            os.makedirs(os.path.dirname(self.db_path))

        create_db = not os.path.exists(self.db_path)
        with sqlite3.connect(self.db_path) as db:
            c = db.cursor()
            if create_db:
                get_logger().info(f"creating service database {self.db_path}")
                c.execute(SERVICE_DB_SCHEMA)
                db.commit()

    def set_service_info(self, name: str, status: str, pid: Optional[int] = None):
        with sqlite3.connect(self.db_path) as db:
            c = db.cursor()
            c.execute("INSERT OR REPLACE INTO services(name, status, pid) VALUES ( ?, ?, ? )", (name, status, pid))
            db.commit()

            get_logger().info(f"service {name} changed status to {status} on pid {pid}")

    def get_service_info(self, name: str) -> ServiceInfo:
        with sqlite3.connect(self.db_path) as db:
            c = db.cursor()
            c.execute("SELECT status, pid FROM services WHERE name = ?", (name,))
            row = c.fetchone()
            if not row:
                return None

            return ServiceInfo(name=name, status=row[0], pid=row[1])

    def delete_service(self, name: str):
        with sqlite3.connect(self.db_path) as db:
            c = db.cursor()
            c.execute("DELETE FROM services WHERE name = ?", (name,))
            db.commit()


class ACEServiceManager:
    def __init__(self, db_path: Optional[str] = None):
        self.db = ACEServiceDB(db_path)

        # map of services running under this manager
        self.services = {}  # key = service name, value = ACEService

        # reference to the event loop we're using
        self.loop = None

    def schedule_service(self, service: ACEService):

        status = self.get_service_status(service.name)
        if status == SERVICE_STATUS_RUNNING:
            raise ServiceAlreadyRunningError(f"service {service.name} is already running")
        elif status == SERVICE_STATUS_DISABLED:
            raise ServiceDisabledError(f"service {service.name} is disabled")
        elif status == SERVICE_STATUS_STALE:
            raise NotImplementedError()

        self.services[service.name] = service
        self.db.set_service_info(service.name, SERVICE_STATUS_STOPPED)

    def stop_service(self, name: str):
        assert isinstance(name, str)

        status = self.get_service_status(name)
        if status != SERVICE_STATUS_RUNNING:
            raise InvalidServiceStateError(f"service {name} was in state {status}")

        pid = self.get_service_pid(name)

        # are we running this right now?
        if pid == os.getpid():
            if name in self.services:
                self.services[name].stop()
            else:
                # this should not happen, but hey
                raise UnknownServiceError(f"service {name} is not loaded in the manager?")
        else:
            # otherwise we have to use signals
            print(f"sending signal to service {name} on {pid}")
            process = psutil.Process(pid)
            process.terminate()
            try:
                process.wait(5)
            except psutil.TimeoutExpired as e:
                print(f"process hung -- killing!")
                process.kill()

    def signal_handler_INT(self):
        get_logger().info("recevied signal INT")
        for name, service in self.services.items():
            service.signal_handler_INT()

    def signal_handler_TERM(self):
        get_logger().info("recevied signal TERM")
        for name, service in self.services.items():
            service.signal_handler_TERM()

    def signal_handler_HUP(self):
        get_logger().info("recevied signal HUP")
        for name, service in self.services.items():
            service.signal_handler_HUP()

    def signal_handler_USR1(self):
        get_logger().info("recevied signal USR1")
        for name, service in self.services.items():
            service.signal_handler_USR1()

    def signal_handler_USR2(self):
        get_logger().info("recevied signal USR2")
        for name, service in self.services.items():
            service.signal_handler_USR2()

    def start(self):

        if self.loop:
            return

        # get or create the async loop to use to run the service(s)
        self.loop = asyncio.get_event_loop()

        # set up all the signal handlers for this process
        self.loop.add_signal_handler(signal.SIGINT, self.signal_handler_INT)
        self.loop.add_signal_handler(signal.SIGTERM, self.signal_handler_TERM)
        self.loop.add_signal_handler(signal.SIGHUP, self.signal_handler_HUP)
        self.loop.add_signal_handler(signal.SIGUSR1, self.signal_handler_USR1)
        self.loop.add_signal_handler(signal.SIGUSR2, self.signal_handler_USR2)

        self.loop.run_until_complete(self.async_start())

    async def async_start(self):
        tasks = []
        for service in self.services.values():
            tasks.append(asyncio.create_task(self.async_start_service(service)))

        done, pending = await asyncio.wait(tasks)

    async def async_start_service(self, service: ACEService):
        self.db.set_service_info(service.name, SERVICE_STATUS_RUNNING, os.getpid())
        await service.start()
        self.db.set_service_info(service.name, SERVICE_STATUS_STOPPED)

    def stop(self):
        pass

    def get_service_status(self, name: str) -> str:
        """Returns the actual status of the given service."""

        info = self.db.get_service_info(name)
        if not info:
            return SERVICE_STATUS_UNKNOWN

        if info.status == SERVICE_STATUS_RUNNING:
            # is it stale?
            try:
                os.kill(info.pid, 0)
                return SERVICE_STATUS_RUNNING
            except OSError:
                return SERVICE_STATUS_STALE

        return info.status
