# vim: ts=4:sw=4:et:cc=120
#

from ace.crypto import initialize_encryption_settings

from tests.systems import DatabaseACETestSystem, RedisACETestSystem, RemoteACETestSystem, DistributedACETestSystem

import pytest


@pytest.fixture(
    scope="session",
    params=[
        "database",
        "redis",
        "remote",
    ],
)
async def system(request, redis):
    import ace.crypto
    from ace.system.distributed import app
    from ace.system.redis import CONFIG_REDIS_HOST, CONFIG_REDIS_PORT

    test_system = None

    if request.param == "database":
        test_system = DatabaseACETestSystem()
    elif request.param == "redis":
        test_system = RedisACETestSystem()

        # pull the unix path from the redislist connection pool
        await test_system.set_config(
            CONFIG_REDIS_HOST, "unix://{}".format(redis.connection_pool.connection_kwargs["path"])
        )
    elif request.param == "remote":
        app.state.system = DistributedACETestSystem()

        # initialize encryption settings with a password of "test"
        app.state.system.encryption_settings = await ace.crypto.initialize_encryption_settings("test")
        app.state.system.encryption_settings.load_aes_key("test")

        # pull the unix path from the redislist connection pool
        await app.state.system.set_config(
            CONFIG_REDIS_HOST, "unix://{}".format(redis.connection_pool.connection_kwargs["path"])
        )

        await app.state.system.initialize()
        await app.state.system.reset()
        root_api_key = await app.state.system.create_api_key("test_root", "test_root", is_admin=True)
        await app.state.system.start()

        test_system = RemoteACETestSystem(api_key=root_api_key.api_key)

    # initialize encryption settings with a password of "test"
    test_system.encryption_settings = await initialize_encryption_settings("test")
    test_system.encryption_settings.load_aes_key("test")

    await test_system.initialize()
    await test_system.start()

    if request.param != "remote":
        # reset system to initial state
        await test_system.reset()

    yield test_system

    await test_system.stop()
    if request.param == "remote":
        await app.state.system.stop()


@pytest.fixture(autouse=True, scope="function")
async def reset_test_system(request, system):
    from ace.system.distributed import app

    await system.reset()
    if isinstance(system, RemoteACETestSystem):
        await app.state.system.reset()
        root_api_key = await app.state.system.create_api_key("test", "root", is_admin=True)
        system.api.api_key = root_api_key.api_key


@pytest.fixture(autouse=True, scope="function")
async def skip_invalid_remote_tests(request, system):
    # if we are testing the remote system then only a handful of tests are valid
    if isinstance(system, RemoteACETestSystem):
        if "ace_remote" not in [_.name for _ in request.node.iter_markers()]:
            pytest.skip("not valid for remote test")


@pytest.fixture
def remote_only(system):
    """Only run this test if the system being testing is a remote system."""
    if not isinstance(system, RemoteACETestSystem):
        pytest.skip("remote-only test")


# def pytest_runtest_setup(item):
# if 'ace_remote' not in [ _.name for _ in item.iter_markers() ]:
# pytest.skip("not valid for remote")
