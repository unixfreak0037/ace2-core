# vim: ts=4:sw=4:et:cc=120
#

import logging

import pytest

from ace.system import get_system, set_system
from ace.system.threaded import ThreadedACESystem


@pytest.fixture(autouse=True, scope="session")
def initialize_modules():
    logging.getLogger().setLevel(logging.DEBUG)
    set_system(ThreadedACESystem())
    get_system().initialize()
    get_system().start()

    yield

    get_system().stop()


@pytest.fixture(autouse=True, scope="function")
def reset_modules():
    get_system().reset()
