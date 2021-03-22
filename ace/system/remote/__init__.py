# vim: ts=4:sw=4:et:cc=120
#
# remote API implementation of the ACE Engine
#

from ace.api.base import AceAPI
from ace.system import ACESystem
from ace.system.remote.alerting import RemoteAlertTrackingInterface
from ace.system.remote.analysis_module import RemoteAnalysisModuleTrackingInterface
from ace.system.remote.analysis_tracking import RemoteAnalysisTrackingInterface
from ace.system.remote.auth import RemoteAuthenticationInterface
from ace.system.remote.caching import RemoteCachingInterface
from ace.system.remote.config import RemoteConfigurationInterface
from ace.system.remote.events import RemoteEventInterface
from ace.system.remote.analysis_request import RemoteAnalysisRequestTrackingInterface
from ace.system.remote.storage import RemoteStorageInterface
from ace.system.remote.work_queue import RemoteWorkQueueManagerInterface


class RemoteACESystem(
    RemoteAlertTrackingInterface,
    RemoteAnalysisRequestTrackingInterface,
    RemoteAuthenticationInterface,
    RemoteCachingInterface,
    RemoteConfigurationInterface,
    RemoteEventInterface,
    RemoteAnalysisModuleTrackingInterface,
    RemoteAnalysisTrackingInterface,
    RemoteStorageInterface,
    RemoteWorkQueueManagerInterface,
    ACESystem,
):
    def get_api(self) -> AceAPI:
        raise NotImplementedError()
