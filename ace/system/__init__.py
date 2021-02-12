# vim: ts=4:sw=4:et:cc=120
#
# global system components

import logging


class ACESystemInterface:
    """The base class that all system interfaces inherit from."""

    def start(self):
        pass

    def stop(self):
        pass

    def reset(self):
        pass


class ACESystem:
    alerting = None
    analysis_tracking = None
    caching = None
    config = None
    events = None
    module_tracking = None
    observable = None
    request_tracking = None
    storage = None
    work_queue = None

    def reset(self):
        self.alerting.reset()
        self.analysis_tracking.reset()
        self.caching.reset()
        self.config.reset()
        self.events.reset()
        self.module_tracking.reset()
        self.request_tracking.reset()
        self.storage.reset()
        self.work_queue.reset()

    # should be called before start() is called
    def initialize(self):
        pass

    # called to start the system
    def start(self):
        self.alerting.start()
        self.analysis_tracking.start()
        self.caching.start()
        self.config.start()
        self.events.start()
        self.module_tracking.start()
        self.request_tracking.start()
        self.storage.start()
        self.work_queue.start()

    # called to stop the system
    def stop(self):
        self.alerting.stop()
        self.analysis_tracking.stop()
        self.caching.stop()
        self.config.stop()
        self.events.stop()
        self.module_tracking.stop()
        self.request_tracking.stop()
        self.storage.stop()
        self.work_queue.stop()


# the global system object that contains references to all the interfaces
global_system = None


def get_system() -> ACESystem:
    """Returns a reference to the global ACESystem object."""
    return global_system


def set_system(system: ACESystem):
    """Sets the reference to the global ACESystem object."""
    global global_system
    global_system = system


def get_logger():
    return logging.getLogger("ace")
