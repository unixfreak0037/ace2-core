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

class FileObservable(Observable):
    def __init__(self, *args, **kwargs):
        super().__init__(F_FILE, *args, **kwargs)
        self._loaded = False
        self.path = None

    def load(self) -> bool:
        """Downloads the contents of the file to the local file system."""
        if self._loaded:
            return True

        # make sure a local storage directory has been created
        self.root.initialize_storage()
        # store the contents of the file inside this directory named after the hash
        self.path = os.path.join(self.root.storage_dir, self.value)
        self._loaded = get_file(self.value, path=self.path)
        return self._loaded

class ThreadedObservableInterface(ObservableInterface):
    """A default implementation that returns the basic Observables appropriate for testing."""
    def create_observable(self, type: str, *args, **kwargs) -> Observable: 
        if type == F_FILE:
            return FileObservable(*args, **kwargs)
        else:
            return Observable(type, *args, **kwargs)
