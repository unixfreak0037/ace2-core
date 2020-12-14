import os
import os.path
import shutil

from datetime import datetime
from pathlib import Path

import pytest
pytest.register_assert_rewrite("tests.ace.requests")

from ace.system import get_system
import ace.system.threaded

@pytest.fixture(autouse=True, scope='session')
def initialize_ace_system():
    ace.system.threaded.initialize()

@pytest.fixture(autouse=True, scope='function')
def reset_ace_system():
    get_system().reset()

@pytest.fixture(autouse=True, scope='session')
def initialize_environment(pytestconfig):
    # where is ACE?
    ace_home = os.getcwd()
    if 'SAQ_HOME' in os.environ:
        ace_home = os.environ['SAQ_HOME']

    import ace
    import ace.constants

    #ace.initialize(
            #ace_home=ace_home, 
            #config_paths=[], 
            #logging_config_path=os.path.join(ace_home, 'etc', 'unittest_logging.ini'), 
            #args=None, 
            #relative_dir=None)

    # load the configuration first
    #if ace.CONFIG['global']['instance_type'] != ace.constants.INSTANCE_TYPE_UNITTEST:
        #raise Exception('*** CRITICAL ERROR ***: invalid instance_type setting in configuration for unit testing')

    # additional logging required for testing
    #ace.test.initialize_unittest_logging()

    # XXX what is this for?
    # create a temporary storage directory
    #test_dir = os.path.join(ace.SAQ_HOME, 'var', 'test')
    #if os.path.exists(test_dir):
        #shutil.rmtree(test_dir)

    #os.makedirs(test_dir)

    yield

