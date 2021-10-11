# vim: sw=4:ts=4:et

import functools


def coreapi(func):
    """Specifies the given function is a core api function."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    wrapper.__coreapi__ = True
    return wrapper
