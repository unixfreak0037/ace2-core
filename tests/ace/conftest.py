# vim: ts=4:sw=4:et:cc=120
#

import asyncio
import logging
import os

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


@pytest.fixture(scope="session", autouse=True)
def initialize_env_vars():
    # ensure a consistent environment
    for var in [
        "ACE_BASE_DIR",
        "ACE_URI",
        "ACE_DB_URL",
        "ACE_REDIS_HOST",
        "ACE_REDIS_PORT",
        "ACE_API_KEY",
        "ACE_CRYPTO_ENCRYPTED_KEY",
        "ACE_CRYPTO_ITERATIONS",
        "ACE_CRYPTO_SALT",
        "ACE_CRYPTO_SALT_SIZE",
        "ACE_CRYPTO_VERIFICATION_KEY",
        "ACE_ADMIN_PASSWORD",
    ]:
        try:
            del os.environ[var]
        except KeyError:
            pass


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
def ace_env(monkeypatch, tmp_path):
    # register a global env with no arguments passed in
    ace.env.register_global_env(ace.env.ACEOperatingEnvironment([]))
    yield
    ace.env.ACE_ENV = None

    # ensure that we use a temporary directory as the base directory for testing
    monkeypatch.setenv("ACE_BASE_DIR", str(tmp_path))
