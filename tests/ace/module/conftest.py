# vim: ts=4:sw=4:et:cc=120
#

import os.path
import os

from ace.crypto import initialize_encryption_settings
from ace.module.manager import AnalysisModuleManager, CONCURRENCY_MODE_PROCESS, CONCURRENCY_MODE_THREADED
from ace.logging import get_logger
from ace.system.distributed import app

from tests.systems import DistributedACETestSystem, RemoteACETestSystem, RemoteACETestSystemProcess

import pytest


@pytest.fixture(scope="session")
def redis_url(redis):
    """Returns the URL to use to connect to the test redis instance."""
    return "unix://{}".format(redis.connection_pool.connection_kwargs["path"])


@pytest.fixture(scope="function", params=[CONCURRENCY_MODE_THREADED, CONCURRENCY_MODE_PROCESS])
async def manager(request, redis, redis_url, tmpdir):

    # initialize the "server side" system
    app.state.system = DistributedACETestSystem()
    from ace.system.redis import CONFIG_REDIS_HOST, CONFIG_REDIS_PORT

    # pull the unix path from the redislist connection pool
    await app.state.system.set_config(CONFIG_REDIS_HOST, redis_url)

    # initialize encryption settings with a password of "test"
    app.state.system.encryption_settings = initialize_encryption_settings("test")
    app.state.system.encryption_settings.load_aes_key("test")

    # set the storage root for the local file system storage
    # app.state.system.storage_root = str(tmpdir)

    await app.state.system.initialize()
    await app.state.system.reset()  # XXX do we need this here?

    app.state.system.root_api_key = await app.state.system.create_api_key("test_root", "test_root", is_admin=True)
    await app.state.system.start()

    # initialize the "client side" system
    system = RemoteACETestSystem(app.state.system.root_api_key)
    await system.initialize()
    await system.start()

    #
    # this is complex so it requires some explanation
    # the manager has a reference to a RemoteACESystem called "system"
    # when manager.system is initialized, it also initializes app.state.system
    # which is the "server" side of the connection (the system that the FastAPI calls use)
    # so when app.state.system gets initialized, everything gets set up (redis, database, encryption settings, etc...)
    #
    # now, the CPUTaskExecutor objects run in their own blank process
    # so they get the class type and init args used to create their own RemoteACESystem to use
    # to communicate with the core (passed in from the manager)
    # (the class type and init args are what are passed in on the Manager constructor)
    #
    # since the "server" side is already set up, we need a different RemoteACESystem type
    # that does NOT re-initialize everything that was already set up
    # so the RemoteACETestSystemClient (note the Client part) is used instead
    # which receives the configuration and settings stored in app.state.system
    #

    if request.param == CONCURRENCY_MODE_THREADED:
        system_class = RemoteACETestSystem
        system_args = (system.api.api_key,)
    elif request.param == CONCURRENCY_MODE_PROCESS:
        system_class = RemoteACETestSystemProcess
        system_args = (redis_url, system.api.api_key, app.state.system.encryption_settings)

    _manager = AnalysisModuleManager(system, system_class, system_args, concurrency_mode=request.param)

    yield _manager

    # stop the distributed system on the "server" side
    await app.state.system.stop()

    # reset redis to default state
    redis.flushall()

    # blast away the database
    if os.path.exists("ace_distributed.db"):
        os.remove("ace_distributed.db")

    # drop the reference to the distributed system on the "server" side
    # this will force this to be recreated every time
    delattr(app.state, "system")
