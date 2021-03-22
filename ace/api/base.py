# vim: ts=4:sw=4:et:cc=120
#

import io

from contextlib import asynccontextmanager
from typing import Union, Any, Optional, AsyncGenerator

from ace.analysis import RootAnalysis, AnalysisModuleType, Observable
from ace.data_model import ContentMetadata, Event, ConfigurationSetting
from ace.system import ACESystem
from ace.system.analysis_request import AnalysisRequest
from ace.system.events import EventHandler


class AceAPI:
    def __init__(self, system: ACESystem, api_key: str = None):
        assert isinstance(system, ACESystem)
        self.system = system
        self.api_key = api_key

    @asynccontextmanager
    async def get_client(self):
        """Returns whatever should be used as the API connection to the remote service."""
        raise NotImplementedError()

    # alerting
    async def register_alert_system(self, name: str) -> bool:
        raise NotImplementedError()

    async def unregister_alert_system(self, name: str) -> bool:
        raise NotImplementedError()

    async def submit_alert(self, root: Union[RootAnalysis, str]) -> bool:
        raise NotImplementedError()

    async def get_alerts(self, name: str, timeout: Optional[int] = None) -> list[str]:
        raise NotImplementedError()

    async def get_alert_count(self, name: str) -> int:
        raise NotImplementedError()

    # analysis module
    async def register_analysis_module_type(self, amt: AnalysisModuleType) -> AnalysisModuleType:
        raise NotImplementedError()

    async def track_analysis_module_type(self, amt: AnalysisModuleType):
        raise NotImplementedError()

    async def get_analysis_module_type(self, name: str) -> Union[AnalysisModuleType, None]:
        raise NotImplementedError()

    async def delete_analysis_module_type(self, amt: Union[AnalysisModuleType, str]):
        raise NotImplementedError()

    async def get_all_analysis_module_types(
        self,
    ) -> list[AnalysisModuleType]:
        raise NotImplementedError()

    # analysis request
    async def track_analysis_request(self, request: AnalysisRequest):
        raise NotImplementedError()

    async def lock_analysis_request(self, request: AnalysisRequest) -> bool:
        raise NotImplementedError()

    async def unlock_analysis_request(self, request: AnalysisRequest) -> bool:
        raise NotImplementedError()

    async def link_analysis_requests(self, source: AnalysisRequest, dest: AnalysisRequest):
        raise NotImplementedError()

    async def get_linked_analysis_requests(self, source: AnalysisRequest) -> list[AnalysisRequest]:
        raise NotImplementedError()

    async def get_analysis_request_by_request_id(self, request_id: str) -> Union[AnalysisRequest, None]:
        raise NotImplementedError()

    async def get_analysis_request_by_cache_key(self, cache_key: str) -> Union[AnalysisRequest, None]:
        raise NotImplementedError()

    async def get_analysis_request(self, key: str) -> Union[AnalysisRequest, None]:
        raise NotImplementedError()

    async def get_analysis_request_by_observable(
        self, observable: Observable, amt: AnalysisModuleType
    ) -> Union[AnalysisRequest, None]:
        raise NotImplementedError()

    async def delete_analysis_request(self, target: Union[AnalysisRequest, str]) -> bool:
        raise NotImplementedError()

    async def get_expired_analysis_requests(
        self,
    ) -> list[AnalysisRequest]:
        raise NotImplementedError()

    async def get_analysis_requests_by_root(self, key: str) -> list[AnalysisRequest]:
        raise NotImplementedError()

    async def clear_tracking_by_analysis_module_type(self, amt: AnalysisModuleType):
        raise NotImplementedError()

    async def submit_analysis_request(self, ar: AnalysisRequest):
        raise NotImplementedError()

    async def process_expired_analysis_requests(
        self,
    ):
        raise NotImplementedError()

    # analysis tracking
    async def get_root_analysis(self, uuid: str) -> Union[RootAnalysis, None]:
        raise NotImplementedError()

    async def track_root_analysis(self, root: RootAnalysis):
        raise NotImplementedError()

    async def update_root_analysis(self, root: RootAnalysis) -> bool:
        raise NotImplementedError()

    async def delete_root_analysis(self, root: Union[RootAnalysis, str]) -> bool:
        raise NotImplementedError()

    async def root_analysis_exists(self, root: Union[RootAnalysis, str]) -> bool:
        raise NotImplementedError()

    async def get_analysis_details(self, uuid: str) -> Any:
        raise NotImplementedError()

    async def track_analysis_details(self, root: RootAnalysis, uuid: str, value: Any) -> bool:
        raise NotImplementedError()

    async def delete_analysis_details(self, uuid: str) -> bool:
        raise NotImplementedError()

    async def analysis_details_exists(self, uuid: str) -> bool:
        raise NotImplementedError()

    # caching
    async def get_cached_analysis_result(
        self, observable: Observable, amt: AnalysisModuleType
    ) -> Union[AnalysisRequest, None]:
        raise NotImplementedError()

    async def cache_analysis_result(self, request: AnalysisRequest) -> Union[str, None]:
        raise NotImplementedError()

    async def delete_expired_cached_analysis_results(
        self,
    ):
        raise NotImplementedError()

    async def delete_cached_analysis_results_by_module_type(self, amt: AnalysisModuleType):
        raise NotImplementedError()

    async def get_total_cache_size(self, amt: Optional[AnalysisModuleType] = None):
        raise NotImplementedError()

    # config
    async def get_config(
        self, key: str, default: Optional[Any] = None, env: Optional[str] = None
    ) -> ConfigurationSetting:
        raise NotImplementedError()

    async def set_config(self, key: str, value: Any, documentation: Optional[str] = None):
        raise NotImplementedError()

    # events
    async def register_event_handler(self, event: str, handler: EventHandler):
        raise NotImplementedError()

    async def remove_event_handler(self, handler: EventHandler, events: Optional[list[str]] = []):
        raise NotImplementedError()

    async def get_event_handlers(self, event: str) -> list[EventHandler]:
        raise NotImplementedError()

    async def fire_event(self, event: Event):
        raise NotImplementedError()

    # processing
    async def process_analysis_request(self, ar: AnalysisRequest):
        raise NotImplementedError()

    # storage
    async def store_content(self, content: Union[bytes, str, io.IOBase], meta: ContentMetadata) -> str:
        raise NotImplementedError()

    async def get_content_bytes(self, sha256: str) -> Union[bytes, None]:
        raise NotImplementedError()

    async def iter_content(self, sha256: str, buffer_size: int) -> Union[AsyncGenerator[bytes, None], None]:
        raise NotImplementedError()

    async def get_content_meta(self, sha256: str) -> Union[ContentMetadata, None]:
        raise NotImplementedError()

    async def delete_content(self, sha256: str) -> bool:
        raise NotImplementedError()

    async def track_content_root(self, sha256: str, root: Union[RootAnalysis, str]):
        raise NotImplementedError()

    async def save_file(self, path: str, **kwargs) -> Union[ContentMetadata, None]:
        raise NotImplementedError()

    async def load_file(self, sha256: str, path: str) -> Union[ContentMetadata, None]:
        raise NotImplementedError()

    # work queue
    async def get_work(self, amt: Union[AnalysisModuleType, str], timeout: int) -> Union[AnalysisRequest, None]:
        raise NotImplementedError()

    async def put_work(self, amt: Union[AnalysisModuleType, str], analysis_request: AnalysisRequest):
        raise NotImplementedError()

    async def get_queue_size(self, amt: Union[AnalysisModuleType, str]) -> int:
        raise NotImplementedError()

    async def delete_work_queue(self, amt: Union[AnalysisModuleType, str]) -> bool:
        raise NotImplementedError()

    async def add_work_queue(self, amt: Union[AnalysisModuleType, str]):
        raise NotImplementedError()

    async def get_next_analysis_request(
        self,
        owner_uuid: str,
        amt: Union[AnalysisModuleType, str],
        timeout: Optional[int] = 0,
        version: Optional[str] = None,
        extended_version: Optional[list[list]] = [],
    ) -> Union[AnalysisRequest, None]:
        raise NotImplementedError()
