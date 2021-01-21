# vim: ts=4:sw=4:et:cc=120
#
# threaded implementation of the ACE Engine
#

from ace.system import ACESystem
from ace.system.threaded.alerting import ThreadedAlertTrackingInterface
from ace.system.threaded.analysis_module import ThreadedAnalysisModuleTrackingInterface
from ace.system.threaded.analysis_request import ThreadedAnalysisRequestTrackingInterface
from ace.system.threaded.analysis_tracking import ThreadedAnalysisTrackingInterface
from ace.system.threaded.caching import ThreadedCachingInterface
from ace.system.threaded.config import ThreadedConfigurationInterface
from ace.system.threaded.events import ThreadedEventInterafce
from ace.system.threaded.locking import ThreadedLockingInterface
from ace.system.threaded.observables import ThreadedObservableInterface
from ace.system.threaded.storage import ThreadedStorageInterface
from ace.system.threaded.work_queue import ThreadedWorkQueueManagerInterface


class ThreadedACESystem(ACESystem):
    """A full implementation of the ACE core that uses Python threads and in-memory data structures.
    Useful for testing and command line one-off analysis."""

    work_queue = ThreadedWorkQueueManagerInterface()
    request_tracking = ThreadedAnalysisRequestTrackingInterface()
    module_tracking = ThreadedAnalysisModuleTrackingInterface()
    analysis_tracking = ThreadedAnalysisTrackingInterface()
    caching = ThreadedCachingInterface()
    storage = ThreadedStorageInterface()
    locking = ThreadedLockingInterface()
    observable = ThreadedObservableInterface()
    config = ThreadedConfigurationInterface()
    alerting = ThreadedAlertTrackingInterface()
    events = ThreadedEventInterafce()
