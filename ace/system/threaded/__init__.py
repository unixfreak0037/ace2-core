# vim: ts=4:sw=4:et:cc=120
#
# threaded implementation of the ACE Engine
#

from ace.system import ACESystem
from ace.system.threaded.alerting import ThreadedAlertTrackingInterface

from ace.system.threaded.events import ThreadedEventInterafce
from ace.system.threaded.observables import ThreadedObservableInterface
from ace.system.threaded.storage import ThreadedStorageInterface
from ace.system.threaded.work_queue import ThreadedWorkQueueManagerInterface


class ThreadedACESystem(ACESystem):
    """A partial implementation of the ACE core that uses Python threads and in-memory data structures.
    Useful for testing and command line one-off analysis."""

    work_queue = ThreadedWorkQueueManagerInterface()
    storage = ThreadedStorageInterface()
    observable = ThreadedObservableInterface()
    alerting = ThreadedAlertTrackingInterface()
    events = ThreadedEventInterafce()
