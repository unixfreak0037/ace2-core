# vim: ts=4:sw=4:et:cc=120
#
# threaded implementation of the ACE Engine
#

from ace.system import ACESystem
from ace.system.threaded.alerting import ThreadedAlertTrackingInterface
from ace.system.threaded.events import ThreadedEventInterafce
from ace.system.threaded.work_queue import ThreadedWorkQueueManagerInterface


class ThreadedACESystem(
    ThreadedAlertTrackingInterface,
    ThreadedEventInterafce,
    ThreadedWorkQueueManagerInterface,
    ACESystem,
):
    """A partial implementation of the ACE core that uses Python threads and in-memory data structures.
    Useful for testing and command line one-off analysis."""

    pass
