# vim: ts=4:sw=4:et:cc=120
#

import io

from typing import Union, Any, Optional

from ace.analysis import RootAnalysis
import ace.system.alerting
import ace.system.analysis_module
import ace.system.analysis_request
import ace.system.analysis_tracking
import ace.system.caching
import ace.system.config
import ace.system.events
import ace.system.locking
import ace.system.observables
import ace.system.processing
import ace.system.storage
import ace.system.work_queue
from ace.api.base import AceAPI

from ace.analysis import RootAnalysis, AnalysisModuleType, Observable
from ace.system.analysis_request import AnalysisRequest
from ace.system.events import EventHandler
from ace.system.storage import ContentMetadata


class LocalAceAPI(AceAPI):
    """Just a wrapper around calling into a local in-memory core system."""

    # alerting
    async def track_alert(self, root: RootAnalysis):
        return ace.system.alerting.track_alert(root)

    # analysis module
    async def register_analysis_module_type(self, amt: AnalysisModuleType) -> AnalysisModuleType:
        return ace.system.analysis_module.register_analysis_module_type(amt)

    async def track_analysis_module_type(self, amt: AnalysisModuleType):
        return ace.system.analysis_module.track_analysis_module_type(amt)

    async def get_analysis_module_type(self, name: str) -> Union[AnalysisModuleType, None]:
        return ace.system.analysis_module.get_analysis_module_type(name)

    async def delete_analysis_module_type(self, amt: Union[AnalysisModuleType, str]):
        return ace.system.analysis_module.delete_analysis_module_type(amt)

    async def get_all_analysis_module_types(
        self,
    ) -> list[AnalysisModuleType]:
        return ace.system.analysis_module.get_all_analysis_module_types()

    # analysis request
    async def track_analysis_request(self, request: AnalysisRequest):
        return ace.system.analysis_request.track_analysis_request(request)

    async def link_analysis_requests(self, source: AnalysisRequest, dest: AnalysisRequest):
        return ace.system.analysis_request.link_analysis_requests(source, dest)

    async def get_linked_analysis_requests(self, source: AnalysisRequest) -> list[AnalysisRequest]:
        return ace.system.analysis_request.get_linked_analysis_requests(source)

    async def get_analysis_request_by_request_id(self, request_id: str) -> Union[AnalysisRequest, None]:
        return ace.system.analysis_request.get_analysis_request_by_request_id(request_id)

    async def get_analysis_request_by_cache_key(self, cache_key: str) -> Union[AnalysisRequest, None]:
        return ace.system.analysis_request.get_analysis_request_by_cache_key(cache_key)

    async def get_analysis_request(self, key: str) -> Union[AnalysisRequest, None]:
        return ace.system.analysis_request.get_analysis_request(key)

    async def get_analysis_request_by_observable(
        self, observable: Observable, amt: AnalysisModuleType
    ) -> Union[AnalysisRequest, None]:
        return ace.system.analysis_request.get_analysis_request_by_observable(observable, amt)

    async def delete_analysis_request(self, target: Union[AnalysisRequest, str]) -> bool:
        return ace.system.analysis_request.delete_analysis_request(target)

    async def get_expired_analysis_requests(
        self,
    ) -> list[AnalysisRequest]:
        return ace.system.analysis_request.get_expired_analysis_requests()

    async def get_analysis_requests_by_root(self, key: str) -> list[AnalysisRequest]:
        return ace.system.analysis_request.get_analysis_requests_by_root(key)

    async def clear_tracking_by_analysis_module_type(self, amt: AnalysisModuleType):
        return ace.system.analysis_request.clear_tracking_by_analysis_module_type(amt)

    async def submit_analysis_request(self, ar: AnalysisRequest):
        return ace.system.analysis_request.submit_analysis_request(ar)

    async def process_expired_analysis_requests(
        self,
    ):
        return ace.system.analysis_request.process_expired_analysis_requests()

    # analysis tracking
    async def get_root_analysis(self, root: Union[RootAnalysis, str]) -> Union[RootAnalysis, None]:
        return ace.system.analysis_tracking.get_root_analysis(root)

    async def track_root_analysis(self, root: RootAnalysis):
        return ace.system.analysis_tracking.track_root_analysis(root)

    async def delete_root_analysis(self, root: Union[RootAnalysis, str]) -> bool:
        return ace.system.analysis_tracking.delete_root_analysis(root)

    async def get_analysis_details(self, uuid: str) -> Any:
        return ace.system.analysis_tracking.get_analysis_details(uuid)

    async def track_analysis_details(self, root: RootAnalysis, uuid: str, value: Any) -> bool:
        return ace.system.analysis_tracking.track_analysis_details(root, uuid, value)

    async def delete_analysis_details(self, uuid: str) -> bool:
        return ace.system.analysis_tracking.delete_analysis_details(uuid)

    # caching
    async def get_cached_analysis_result(
        self, observable: Observable, amt: AnalysisModuleType
    ) -> Union[AnalysisRequest, None]:
        return ace.system.caching.get_cached_analysis_result(observable, amt)

    async def cache_analysis_result(self, request: AnalysisRequest) -> Union[str, None]:
        return ace.system.caching.cache_analysis_result(request)

    async def delete_expired_cached_analysis_results(
        self,
    ):
        return ace.system.caching.delete_expired_cached_analysis_results()

    async def delete_cached_analysis_results_by_module_type(self, amt: AnalysisModuleType):
        return ace.system.caching.delete_cached_analysis_results_by_module_type(amt)

    async def get_total_cache_size(self, amt: Optional[AnalysisModuleType] = None):
        return ace.system.caching.get_total_cache_size(amt)

    # config
    async def get_config(self, key: str, default: Optional[Any] = None) -> Any:
        return ace.system.get_config(key, default)

    async def set_config(self, key: str, value: Any):
        return ace.system.set_config(key, value)

    # events
    async def register_event_handler(self, event: str, handler: EventHandler):
        return ace.system.events.register_event_handler(event, handler)

    async def remove_event_handler(self, handler: EventHandler, events: Optional[list[str]] = []):
        return ace.system.events.remove_event_handler(handler, events)

    async def get_event_handlers(self, event: str) -> list[EventHandler]:
        return ace.system.events.get_event_handlers(event)

    async def fire_event(self, event: str, *args, **kwargs):
        return ace.system.events.fire_event(event, *args, **kwargs)

    # locking
    async def get_lock_owner(self, lock_id: str) -> Union[str, None]:
        return ace.system.locking.get_lock_owner(lock_id)

    async def get_owner_wait_target(self, owner_id: str) -> Union[str, None]:
        return ace.system.locking.get_owner_wait_target(owner_id)

    async def track_wait_target(self, lock_id: Union[str, None], owner_id: str):
        return ace.system.locking.track_wait_target(lock_id, owner_id)

    async def clear_wait_target(self, owner_id: str):
        return ace.system.locking.clear_wait_target(owner_id)

    async def is_locked(self, lock_id: str) -> bool:
        return ace.system.locking.is_locked(lock_id)

    async def get_lock_count(
        self,
    ) -> int:
        return ace.system.locking.get_lock_count()

    async def acquire(
        self,
        lock_id: str,
        owner_id: Optional[str] = None,
        timeout: Union[int, float, None] = None,
        lock_timeout: Union[int, float, None] = None,
    ) -> bool:
        return ace.system.locking.acquire(lock_id, owner_id, timeout, lock_timeout)

    async def release(self, lock_id: str, owner_id: Optional[str] = None) -> bool:
        return ace.system.locking.release(lock_id, owner_id)

    # observables
    async def create_observable(self, type: str, *args, **kwargs) -> Observable:
        return ace.system.observables.create_observable(type, *args, **kwargs)

    # processing
    async def process_analysis_request(self, ar: AnalysisRequest):
        return ace.system.processing.process_analysis_request(ar)

    # storage
    async def store_content(self, content: Union[bytes, str, io.IOBase], meta: ContentMetadata) -> str:
        return ace.system.storage.store_content(content, meta)

    async def get_content_bytes(self, sha256: str) -> Union[bytes, None]:
        return ace.system.storage.get_content_bytes(sha256)

    async def get_content_stream(self, sha256: str) -> Union[io.IOBase, None]:
        return ace.system.storage.get_content_stream(sha256)

    async def get_content_meta(self, sha256: str) -> Union[ContentMetadata, None]:
        return ace.system.storage.get_content_meta(sha256)

    async def delete_content(self, sha256: str) -> bool:
        return ace.system.storage.delete_content(sha256)

    async def track_content_root(self, sha256: str, root: Union[RootAnalysis, str]):
        return ace.system.storage.track_content_root(sha256, root)

    # work queue
    async def get_work(self, amt: Union[AnalysisModuleType, str], timeout: int) -> Union[AnalysisRequest, None]:
        return ace.system.work_queue.get_work(amt, timeout)

    async def put_work(self, amt: Union[AnalysisModuleType, str], analysis_request: AnalysisRequest):
        return ace.system.work_queue.put_work(amt, analysis_request)

    async def get_queue_size(self, amt: Union[AnalysisModuleType, str]) -> int:
        return ace.system.work_queue.get_work(amt)

    async def delete_work_queue(self, amt: Union[AnalysisModuleType, str]) -> bool:
        return ace.system.work_queue.get_work(amt)

    async def add_work_queue(self, amt: Union[AnalysisModuleType, str]):
        return ace.system.work_queue.get_work(amt)

    async def get_next_analysis_request(
        self, owner_uuid: str, amt: Union[AnalysisModuleType, str], timeout: Optional[int] = 0
    ) -> Union[AnalysisRequest, None]:
        return ace.system.work_queue.get_work(owner_uuid, amt, timeout)
