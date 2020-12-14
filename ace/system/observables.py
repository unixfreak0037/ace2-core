# vim: ts=4:sw=4:et:cc=120
#

import datetime

from typing import Union

from ace.analysis import Observable
from ace.constants import F_FILE
from ace.system import get_system, ACESystemInterface

class ObservableInterface(ACESystemInterface):
    def create_observable(self, type: str, *args, **kwargs) -> Observable:
        raise NotImplementedError()

def create_observable(type: str, *args, **kwargs) -> Observable:
    if get_system().observable is None:
        return Observable(type, *args, **kwargs)

    return get_system().observable.create_observable(type, *args, **kwargs)

