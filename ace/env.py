# vim: ts=4:sw=4:et:cc=120

import os
import os.path

from ace.cli import get_args
from ace.constants import ACE_URI, ACE_API_KEY, ACE_PACKAGE_DIR


def get_uri() -> str:
    if ACE_URI in os.environ:
        return os.environ[ACE_URI]

    return get_args().uri


def get_api_key() -> str:
    if ACE_API_KEY in os.environ:
        return os.environ[ACE_API_KEY]

    return get_args().api_key


def get_package_dir() -> str:

    if get_args().package_dir:
        return get_args().package_dir

    if ACE_PACKAGE_DIR in os.environ:
        return os.environ[ACE_PACKAGE_DIR]

    return os.path.join(os.path.expanduser("~"), ".ace", "packages")
