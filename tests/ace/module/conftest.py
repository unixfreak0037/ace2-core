# vim: ts=4:sw=4:et:cc=120
#

import logging
import os
import os.path

import pytest

from ace.api import set_api
from ace.api.local import LocalAceAPI
from ace.system import get_system, set_system
from ace.system.threaded import ThreadedACESystem
from ace.system.database import DatabaseACESystem

# XXX copy-pasta
class DatabaseACETestSystem(DatabaseACESystem, ThreadedACESystem):

    # running this out of memory does not work due to the multithreading
    # each connection gets its own thread (thanks to session scoping)
    # and this in-memory db only exists for the connection its on
    # engine = create_engine("sqlite://")
    #db_url = "sqlite:///ace.db"
    db_url = "sqlite://"

    def reset(self):
        super().reset()

        self.db = None

        # remove the temporary file we used
        #if os.path.exists("ace.db"):
            #os.remove("ace.db")

        # re-initialize and create the database
        self.initialize()
        self.create_database()

    def create_database(self):
        from ace.system.database import Base

        Base.metadata.bind = self.engine
        Base.metadata.create_all()

    def stop(self):
        super().stop()

        #if os.path.exists("ace.db"):
            #os.remove("ace.db")


@pytest.fixture(autouse=True, scope="session")
def initialize_modules():
    logging.getLogger().setLevel(logging.DEBUG)
    set_system(DatabaseACETestSystem())
    set_api(LocalAceAPI())
    get_system().initialize()
    get_system().start()

    yield

    get_system().stop()


@pytest.fixture(autouse=True, scope="function")
def reset_modules():
    get_system().reset()
