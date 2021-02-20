import logging
import os
import os.path

import ace.system.distributed

from ace.system import ACESystem, get_system, set_system, get_logger
from ace.system.database import DatabaseACESystem, CONFIG_DB_URL, CONFIG_DB_KWARGS

from ace.system.redis import RedisACESystem
from ace.system.threaded import ThreadedACESystem
from tests.systems import ThreadedACETestSystem, DatabaseACETestSystem, RedisACETestSystem

import pytest


@pytest.fixture(
    autouse=True,
    scope="session",
    params=[
        DatabaseACETestSystem,
        RedisACETestSystem,
    ],
)
def initialize_ace_system(request):
    get_logger().setLevel(logging.DEBUG)
    set_system(request.param())
    get_system().initialize()
    get_system().start()

    yield

    get_system().stop()


@pytest.fixture(autouse=True, scope="function")
def reset_ace_system():
    get_system().reset()
