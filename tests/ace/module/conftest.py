# vim: ts=4:sw=4:et:cc=120
#

import logging
import os
import os.path

import pytest

from ace.api import set_api
from ace.api.local import LocalAceAPI
from ace.api.remote import RemoteAceAPI
from ace.system import get_system, set_system, get_logger
from ace.system.distributed import app

from tests.systems import DistributedACETestSystem


@pytest.fixture(
    autouse=True,
    params=[
        LocalAceAPI,
        RemoteAceAPI,
    ],
    scope="session",
)
def initialize(request):
    get_logger().setLevel(logging.DEBUG)
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
def reset():
    get_system().reset()
