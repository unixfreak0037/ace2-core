# vim: ts=4:sw=4:et:cc=120
#

import logging

import pytest


@pytest.fixture(autouse=True, scope="session")
def initialize_logging():
    logging.getLogger("redislite").setLevel(logging.WARNING)
