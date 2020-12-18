# vim: sw=4:ts=4:et:cc=120

from ace.system import ACESystem, set_system
from ace.system.threaded.alerting import ThreadedAlertTrackingInterface
from ace.system.database.analysis_module import DatabaseAnalysisModuleTrackingInterface
from ace.system.database.analysis_request import DatabaseAnalysisRequestTrackingInterface
from ace.system.database.analysis_tracking import DatabaseAnalysisTrackingInterface
from ace.system.database.caching import DatabaseCachingInterface
from ace.system.database.observables import DatabaseObservableInterface
from ace.system.threaded.config import ThreadedConfigurationInterface
from ace.system.threaded.events import ThreadedEventInterafce
from ace.system.threaded.locking import ThreadedLockingInterface
from ace.system.threaded.storage import ThreadedStorageInterface
from ace.system.threaded.work_queue import ThreadedWorkQueueManagerInterface


class DatabaseACESystem(ACESystem):
    alerting = ThreadedAlertTrackingInterface()
    analysis_tracking = DatabaseAnalysisTrackingInterface()
    caching = DatabaseCachingInterface()
    config = ThreadedConfigurationInterface()
    events = ThreadedEventInterafce()
    locking = ThreadedLockingInterface()
    module_tracking = DatabaseAnalysisModuleTrackingInterface()
    observable = DatabaseObservableInterface()
    request_tracking = DatabaseAnalysisRequestTrackingInterface()
    storage = ThreadedStorageInterface()
    work_queue = ThreadedWorkQueueManagerInterface()

    def reset(self):
        self.alerting.reset()
        self.config.reset()
        self.events.reset()
        self.locking.reset()
        self.storage.reset()
        self.work_queue.reset()


def initialize():
    set_system(DatabaseACESystem())
