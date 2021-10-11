# vim: sw=4:ts=4:et
#
# ACE Services
# These are wrappers around the concept of a process that executes as part of
# ACE and optionally in the background.
#

#
# NOTES
# - services are local to the system running them
# - the status of services are stored in a local sqlite database
# - services themselves are not async, but they do start the main async loop
#

import asyncio
import os, os.path
import resource
import signal
import sys
import sqlite3

from typing import Optional

from ace.constants import (
    SERVICE_STATUS_RUNNING,
    SERVICE_STATUS_STOPPED,
    SERVICE_STATUS_STALE,
    SERVICE_STATUS_DISABLED,
)

from ace.logging import get_logger


class ACEService:

    # the name of the service (must be overridden)
    name: str = None

    # a useful description for the person who is managing the system
    description: str = None

    def __init__(self):
        # event that gets set when the service should shut down
        self.shutdown_event = asyncio.Event()

    async def run(self):
        """Main execution routine of the service. Must be overridden. Does not return until service stops."""
        raise NotImplementedError()

    # TODO
    def get_dependencies(self) -> list[str]:
        """Returns a list of services that this service depends on.
        Dependencies are stored in the configuration settings for the service at
        /service/{name}/dependencies"""
        raise NotImplementedError()

    async def start(self):
        get_logger().info(f"starting service {self.name}")
        await self.run()
        get_logger().info(f"stopped service {self.name}")

    async def stop(self):
        self.shutdown_event.set()

    async def debug(self):
        pass

    def signal_handler_INT(self):
        if self.shutdown_event.is_set():
            sys.exit(1)

        self.shutdown_event.set()

    def signal_handler_TERM(self):
        if self.shutdown_event.is_set():
            sys.exit(1)

        self.shutdown_event.set()

    def signal_handler_HUP(self):
        pass

    def signal_handler_USR1(self):
        pass

    def signal_handler_USR2(self):
        pass
