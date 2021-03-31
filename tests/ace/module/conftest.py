# vim: ts=4:sw=4:et:cc=120
#

from ace.crypto import initialize_encryption_settings
from ace.logging import get_logger
from ace.system.distributed import app

from tests.systems import DistributedACETestSystem, RemoteACETestSystem

import pytest


@pytest.fixture(scope="session")
async def remote_system(redis):
    app.state.system = DistributedACETestSystem()
    from ace.system.redis import CONFIG_REDIS_HOST, CONFIG_REDIS_PORT

    # pull the unix path from the redislist connection pool
    await app.state.system.set_config(
        CONFIG_REDIS_HOST, "unix://{}".format(redis.connection_pool.connection_kwargs["path"])
    )

    # initialize encryption settings with a password of "test"
    app.state.system.encryption_settings = initialize_encryption_settings("test")
    app.state.system.encryption_settings.load_aes_key("test")

    # await app.state.system.initialize()
    await app.state.system.reset()

    app.state.system.root_api_key = await app.state.system.create_api_key("test_root", "test_root", is_admin=True)
    await app.state.system.start()

    test_system = RemoteACETestSystem()
    await test_system.initialize()

    # copy the auto generated root api key to the client
    test_system.api.api_key = app.state.system.root_api_key
    get_logger().info(f"using api key {test_system.api.api_key}")

    await test_system.start()

    yield test_system

    await test_system.stop()
    await app.state.system.stop()


@pytest.fixture(autouse=True, scope="function")
async def reset_remote_system(remote_system):
    await app.state.system.reset()
    app.state.system.root_api_key = await app.state.system.create_api_key("test", "root", is_admin=True)
    remote_system.api.api_key = app.state.system.root_api_key
