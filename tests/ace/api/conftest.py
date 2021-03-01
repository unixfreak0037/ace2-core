# vim: ts=4:sw=4:et:cc=120
#

import os
import os.path
import logging

from ace.api import set_api
from ace.api.local import LocalAceAPI
from ace.api.remote import RemoteAceAPI
from ace.system import get_system, set_system
from ace.system.distributed import app
from tests.systems import DistributedACETestSystem

import pytest


@pytest.fixture(
    autouse=True,
    params=[
        LocalAceAPI,
        RemoteAceAPI,
    ],
    scope="session",
)
def initialize_api(request):
    logging.getLogger().setLevel(logging.DEBUG)
    set_system(DistributedACETestSystem())
    api = request.param()
    # configure to client to directly use the application object
    # see https://fastapi.tiangolo.com/advanced/async-tests/
    api.client_kwargs = {"app": app, "base_url": "http://test"}
    set_api(api)
    get_system().initialize()
    get_system().start()

    yield

    get_system().stop()


@pytest.fixture(autouse=True, scope="function")
def reset_modules():
    get_system().reset()
