# vim: ts=4:sw=4:et:cc=120
#

import contextlib
import threading

import rpyc
from rpyc.utils.server import ThreadedServer


@contextlib.contextmanager
def get_distributed_connection(*args, **kwargs):
    _connection = rpyc.connect("localhost", 12345)  # XXX
    try:
        yield _connection
    finally:
        try:
            _connection.close()
        except:
            pass


from ace.system import ACESystem, set_system
from ace.system.threaded.alerting import ThreadedAlertTrackingInterface
from ace.system.threaded.analysis_module import ThreadedAnalysisModuleTrackingInterface
from ace.system.threaded.analysis_request import ThreadedAnalysisRequestTrackingInterface
from ace.system.threaded.analysis_tracking import ThreadedAnalysisTrackingInterface
from ace.system.threaded.events import ThreadedEventInterafce
from ace.system.threaded.config import ThreadedConfigurationInterface
from ace.system.threaded.caching import ThreadedCachingInterface
from ace.system.distributed.locking import DistributedLockingInterfaceService, DistributedLockingInterfaceClient
from ace.system.threaded.observables import ThreadedObservableInterface
from ace.system.threaded.storage import ThreadedStorageInterface
from ace.system.threaded.work_queue import ThreadedWorkQueueManagerInterface


class DistributedACESystem(ACESystem):
    alerting = ThreadedAlertTrackingInterface()
    analysis_tracking = ThreadedAnalysisTrackingInterface()
    caching = ThreadedCachingInterface()
    config = ThreadedConfigurationInterface()
    events = ThreadedEventInterafce()
    locking = DistributedLockingInterfaceClient()
    module_tracking = ThreadedAnalysisModuleTrackingInterface()
    observable = ThreadedObservableInterface()
    request_tracking = ThreadedAnalysisRequestTrackingInterface()
    storage = ThreadedStorageInterface()
    work_queue = ThreadedWorkQueueManagerInterface()


locking_service = None


def initialize():
    global locking_service

    locking_service = ThreadedServer(DistributedLockingInterfaceService(), port=12345)  # XXX
    locking_service_thread = threading.Thread(target=locking_service.start, name="Locking Service")
    locking_service_thread.start()

    set_system(DistributedACESystem())


def cleanup():
    locking_service.close()
