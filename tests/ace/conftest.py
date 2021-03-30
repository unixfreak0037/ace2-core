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


@pytest.fixture(
    autouse=True,
    scope="session",
    params=[
        "database",
        "redis",
        # "remote",
    ],
)
async def system(request, redis):

    test_system = None
    get_logger().setLevel(logging.DEBUG)

    app.state.system = None
    if request.param == "remote":
        app.state.system = DistributedACETestSystem()

        # initialize encryption settings with a password of "test"
        app.state.system.encryption_settings = ace.crypto.initialize_encryption_settings("test")
        app.state.system.encryption_settings.load_aes_key("test")
        await app.state.system.initialize()
        await app.state.system.reset()
        app.state.system.root_api_key = await app.state.system.create_api_key("test_root", "test_root", is_admin=True)
        app.state.system.start()

    if request.param == "database":
        test_system = DatabaseACETestSystem()
        # initialize encryption settings with a password of "test"
        test_system.encryption_settings = ace.crypto.initialize_encryption_settings("test")
        test_system.encryption_settings.load_aes_key("test")
    elif request.param == "redis":
        test_system = RedisACETestSystem()
        from ace.system.redis import CONFIG_REDIS_HOST, CONFIG_REDIS_PORT

        await test_system.set_config(CONFIG_REDIS_HOST, redis.client_port())
        # initialize encryption settings with a password of "test"
        test_system.encryption_settings = ace.crypto.initialize_encryption_settings("test")
        test_system.encryption_settings.load_aes_key("test")
    elif request.param == "remote":
        # these two systems share the same database and redis instance
        test_system = RemoteACETestSystem()

    await test_system.initialize()

    # copy the auto generated root api key to the client
    if request.param == "remote":
        test_system.api.api_key = app.state.system.root_api_key
        get_logger().info(f"using api key {test_system.api.api_key}")

    test_system.start()

    if request.param != "remote":
        # reset system to initial state
        await test_system.reset()

    yield test_system

    test_system.stop()
    if request.param == "remote":
        app.state.system.stop()


@pytest.fixture(autouse=True, scope="function")
async def reset_ace_system(system):
    if not isinstance(system, RemoteACETestSystem):
        await system.reset()
    else:
        # XXX temp hack until we implement events in the distributed interface
        system.event_handlers = {}

    if app.state.system:
        await app.state.system.reset()
        app.state.system.root_api_key = await app.state.system.create_api_key("test", "root", is_admin=True)
        system.api.api_key = app.state.system.root_api_key
