# vim: ts=4:sw=4:et:cc=120
#

import datetime
import os.path

from typing import Union

from ace.analysis import Observable
from ace.constants import F_FILE
from ace.system import get_system
from ace.system.observables import ObservableInterface
from ace.system.storage import get_file


class DatabaseObservableInterface(ObservableInterface):
    """A default implementation that returns the basic Observables appropriate for testing."""

    def create_observable(self, type: str, *args, **kwargs) -> Observable:
        return Observable(type, *args, **kwargs)
