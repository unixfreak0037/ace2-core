# vim: ts=4:sw=4:et:cc=120
#

import asyncio
import logging

import pytest

import ace.crypto
import ace.env
import ace.system.distributed

from ace.logging import get_logger
from ace.system.distributed import app

from tests.systems import (
    ThreadedACETestSystem,
    DatabaseACETestSystem,
    RedisACETestSystem,
    RemoteACETestSystem,
    DistributedACETestSystem,
)

# from docker import DockerClient
# from yellowbox.extras.redis import RedisService

from redislite import Redis


@pytest.fixture(autouse=True, scope="session")
def initialize_logging():
    logging.getLogger("redislite").setLevel(logging.WARNING)
    logging.getLogger().setLevel(logging.DEBUG)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def redis():
    try:
        redis_connection = Redis("ace.rdb")
        yield redis_connection
    finally:
        redis_connection.close()


@pytest.fixture(scope="function", autouse=True)
def ace_env(monkeypatch):
    # register a global env with no arguments passed in
    ace.env.register_global_env(ace.env.ACEOperatingEnvironment([]))
    yield
    ace.env.ACE_ENV = None
