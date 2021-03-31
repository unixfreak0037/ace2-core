# vim: ts=4:sw=4:et:cc=120
#

from ace.crypto import initialize_encryption_settings

from tests.systems import DatabaseACETestSystem, RedisACETestSystem

import pytest


@pytest.fixture(
    scope="session",
    params=[
        "database",
        "redis",
    ],
)
async def system(request, redis):
    test_system = None

    if request.param == "database":
        test_system = DatabaseACETestSystem()
    elif request.param == "redis":
        test_system = RedisACETestSystem()
        from ace.system.redis import CONFIG_REDIS_HOST, CONFIG_REDIS_PORT

        # pull the unix path from the redislist connection pool
        await test_system.set_config(
            CONFIG_REDIS_HOST, "unix://{}".format(redis.connection_pool.connection_kwargs["path"])
        )

    # initialize encryption settings with a password of "test"
    test_system.encryption_settings = initialize_encryption_settings("test")
    test_system.encryption_settings.load_aes_key("test")

    await test_system.initialize()
    await test_system.start()

    # reset system to initial state
    await test_system.reset()

    yield test_system

    await test_system.stop()


@pytest.fixture(autouse=True, scope="function")
async def reset_test_system(system):
    await system.reset()
