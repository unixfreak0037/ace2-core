import logging

import ace.system.threaded
import ace.system.database
import ace.system.distributed

from ace.system import get_system

import pytest


@pytest.fixture(
    autouse=True,
    scope="session",
    params=[
        (ace.system.threaded.initialize, None),
        (ace.system.database.initialize, None),
        (ace.system.distributed.initialize, ace.system.distributed.cleanup),
    ],
)
def initialize_ace_system(request):
    init_func, cleanup_func = request.param
    logging.getLogger().setLevel(logging.DEBUG)
    init_func()

    yield

    if cleanup_func:
        cleanup_func()


@pytest.fixture(autouse=True, scope="function")
def reset_ace_system():
    get_system().reset()
