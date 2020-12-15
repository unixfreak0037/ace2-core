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


# the global system object that contains references to all the interfaces
ace = ACESystem()


def get_system() -> ACESystem:
    return ace


def set_system(system: ACESystem):
    global ace
    ace = system
