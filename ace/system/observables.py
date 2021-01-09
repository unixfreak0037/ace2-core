# vim: ts=4:sw=4:et:cc=120
#

import datetime

from typing import Union

from ace.analysis import Observable
from ace.system import get_system, ACESystemInterface

#
# this class is used to create Observable instances
# for example, an implementation could return a custom FileObservable class for F_FILE type observables
# that implements additional functionality
#


class ObservableInterface(ACESystemInterface):
    """Provides an interface to instantiate overloaded Observable classes based on type."""

    def create_observable(self, type: str, *args, **kwargs) -> Observable:
        """Returns a new Observable-based object with the given parameters."""
        raise NotImplementedError()


def create_observable(type: str, *args, **kwargs) -> Observable:
    if get_system().observable is None:
        return Observable(type, *args, **kwargs)

    return get_system().observable.create_observable(type, *args, **kwargs)
