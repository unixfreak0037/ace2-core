# vim: ts=4:sw=4:et:cc=120
#
# remote API implementation of the ACE Engine
#

from typing import Optional

from ace.api.base import AceAPI
from ace.api.remote import RemoteAceAPI
from ace.system import ACESystem
from ace.system.remote.alerting import RemoteAlertTrackingInterface
from ace.system.remote.analysis_tracking import RemoteAnalysisTrackingInterface
from ace.system.remote.auth import RemoteAuthenticationInterface
from ace.system.remote.caching import RemoteCachingInterface
from ace.system.remote.config import RemoteConfigurationInterface
from ace.system.remote.events import RemoteEventInterface
from ace.system.remote.module_tracking import RemoteAnalysisModuleTrackingInterface
from ace.system.remote.request_tracking import RemoteAnalysisRequestTrackingInterface
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
    def __init__(
        self, url, api_key, *args, client_args: Optional[list] = None, client_kwargs: Optional[dict] = None, **kwargs
    ):
        super().__init__(*args, *kwargs)

        self.url = url
        self.api_key = api_key
        self.api = RemoteAceAPI(self, api_key, url, client_args=client_args, client_kwargs=client_kwargs)

    def get_api(self) -> AceAPI:
        return self.api
