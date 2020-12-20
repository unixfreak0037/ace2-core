# vim: ts=4:sw=4:et:cc=120
#
# global system components


class ACESystemInterface:
    """The base class that all system interfaces inherit from."""

    pass


class ACESystem:
    alerting = None
    analysis_tracking = None
    caching = None
    config = None
    events = None
    locking = None
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
        self.locking.reset()
        self.module_tracking.reset()
        self.request_tracking.reset()
        self.storage.reset()
        self.work_queue.reset()


# the global system object that contains references to all the interfaces
ace = ACESystem()


def get_system() -> ACESystem:
    """Returns a reference to the global ACESystem object."""
    return ace


def set_system(system: ACESystem):
    """Sets the reference to the global ACESystem object."""
    global ace
    ace = system
