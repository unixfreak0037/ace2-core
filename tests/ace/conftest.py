import logging

import ace.system.threaded
import ace.system.database

from ace.system import get_system

import pytest


@pytest.fixture(autouse=True, scope="session", params=[
    ace.system.threaded.initialize,
    ace.system.database.initialize,
])
def initialize_ace_system(request):
    request.param()
    logging.getLogger().setLevel(logging.DEBUG)


@pytest.fixture(autouse=True, scope="function")
def reset_ace_system():
    get_system().reset()
