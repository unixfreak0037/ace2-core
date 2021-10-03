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
        self,
        url: str,
        api_key: str,
        *args,
        client_args: Optional[list] = None,
        client_kwargs: Optional[dict] = None,
        **kwargs
    ):
        super().__init__(*args, *kwargs)

        assert isinstance(url, str) and url
        assert isinstance(api_key, str) and api_key
        assert client_args is None or isinstance(client_args, list)
        assert client_kwargs is None or isinstance(client_kwargs, dict)

        self.url = url
        self.api_key = api_key
        self.client_args = client_args
        self.client_kwargs = client_kwargs
        self.api = RemoteAceAPI(self, api_key, url, client_args=client_args, client_kwargs=client_kwargs)

    def get_api(self) -> AceAPI:
        # if the api key changed then create a new api object to use
        # if self.api_key != self.api.api_key:
        # breakpoint()
        # self.api = RemoteAceAPI(self, self.api_key, self.url, client_args=self.client_args, client_kwargs=self.client_kwargs)

        return self.api
