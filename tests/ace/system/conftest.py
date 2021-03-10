import asyncio
import logging
import os
import os.path

import ace.crypto
import ace.system.distributed

from ace.system import ACESystem, get_logger
from ace.system.database import DatabaseACESystem, CONFIG_DB_URL, CONFIG_DB_KWARGS
from ace.system.distributed import app

from ace.system.redis import RedisACESystem
from ace.system.threaded import ThreadedACESystem
from tests.systems import (
    ThreadedACETestSystem,
    DatabaseACETestSystem,
    RedisACETestSystem,
    RemoteACETestSystem,
    DistributedACETestSystem,
)

import pytest

# the global system we're testing
test_system = None


# @pytest.fixture(scope="session")
# def event_loop():
# loop = asyncio.get_event_loop_policy().new_event_loop()
# yield loop
# loop.close()


#
# note that we don't test the RemoteACESystem here because it only implements
# the handful of functions actually used remotely, where these tests test the
# entire system
#


@pytest.fixture(
    autouse=True,
    scope="session",
    params=[
        "database",
        "redis",
        "remote",
    ],
)
async def system(request):
    global test_system

    get_logger().setLevel(logging.DEBUG)

    app.state.system = None
    if request.param == "remote":
        app.state.system = DistributedACETestSystem()

        # initialize encryption settings with a password of "test"
        app.state.system.encryption_settings = ace.crypto.initialize_encryption_settings("test")
        app.state.system.encryption_settings.load_aes_key("test")
        await app.state.system.initialize()
        await app.state.system.reset()
        app.state.system.root_api_key = await app.state.system.create_api_key("test", "root")
        app.state.system.start()

    if request.param == "database":
        test_system = DatabaseACETestSystem()
    elif request.param == "redis":
        test_system = RedisACETestSystem()
    elif request.param == "remote":
        # these two systems share the same database and redis instance
        test_system = RemoteACETestSystem()

    # initialize encryption settings with a password of "test"
    test_system.encryption_settings = ace.crypto.initialize_encryption_settings("test")
    test_system.encryption_settings.load_aes_key("test")

    await test_system.initialize()

    # copy the auto generated root api key to the client
    if request.param == "remote":
        test_system.api.api_key = app.state.system.root_api_key

    test_system.start()

    if request.param != "remote":
        # reset system to initial state
        await test_system.reset()

    yield test_system

    test_system.stop()
    if request.param == "remote":
        app.state.system.stop()


@pytest.fixture(autouse=True, scope="function")
async def reset_ace_system():
    await test_system.reset()
    if app.state.system:
        app.state.system.root_api_key = await app.state.system.create_api_key("test", "root")
        test_system.api.api_key = app.state.system.root_api_key
