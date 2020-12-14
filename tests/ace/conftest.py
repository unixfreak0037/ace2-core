import pytest

from ace.system import get_system
import ace.system.threaded

@pytest.fixture(autouse=True, scope='session')
def initialize_ace_system():
    ace.system.threaded.initialize()

@pytest.fixture(autouse=True, scope='function')
def reset_ace_system():
    get_system().reset()
