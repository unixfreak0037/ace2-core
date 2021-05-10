# vim: sw=4:ts=4:et

import functools

import pytz
import tzlocal

import ace
import ace.cli
import ace.packages_cli
import ace.service.cli

from ace.packages import get_package_manager

# local timezone
LOCAL_TIMEZONE = pytz.timezone(tzlocal.get_localzone().zone)


def coreapi(func):
    """Specifies the given function is a core api function."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    wrapper.__coreapi__ = True
    return wrapper
