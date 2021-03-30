# vim: ts=4:sw=4:et:cc=120
#

import asyncio
import logging

import pytest

import ace.crypto
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

from docker import DockerClient
from yellowbox.extras.redis import RedisService


@pytest.fixture(autouse=True, scope="session")
def initialize_logging():
    logging.getLogger("redislite").setLevel(logging.WARNING)
    get_logger().setLevel(logging.DEBUG)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def redis():
    docker_client = DockerClient.from_env()
    with RedisService.run(docker_client) as redis:
        yield redis
        docker_client.close()
