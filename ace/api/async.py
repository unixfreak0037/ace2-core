# vim: ts=4:sw=4:et:cc=120
#


class AsyncAceAPI(AceAPI):
    # alerting
    async def track_alert(self, root: RootAnalysis):
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
    async def get_root_analysis(self, root: Union[RootAnalysis, str]) -> Union[RootAnalysis, None]:
        raise NotImplementedError()

    async def track_root_analysis(self, root: RootAnalysis):
        raise NotImplementedError()

    async def delete_root_analysis(self, root: Union[RootAnalysis, str]) -> bool:
        raise NotImplementedError()

    async def get_analysis_details(self, uuid: str) -> Any:
        raise NotImplementedError()

    async def track_analysis_details(self, root: RootAnalysis, uuid: str, value: Any) -> bool:
        raise NotImplementedError()

    async def delete_analysis_details(self, uuid: str) -> bool:
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
    async def get_config(self, key: str, default: Optional[Any] = None) -> Any:
        raise NotImplementedError()

    async def set_config(self, key: str, value: Any):
        raise NotImplementedError()

    # events
    async def register_event_handler(self, event: str, handler: EventHandler):
        raise NotImplementedError()

    async def remove_event_handler(self, handler: EventHandler, events: Optional[list[str]] = []):
        raise NotImplementedError()

    async def get_event_handlers(self, event: str) -> list[EventHandler]:
        raise NotImplementedError()

    async def fire_event(self, event: str, *args, **kwargs):
        raise NotImplementedError()

    # locking
    async def get_lock_owner(self, lock_id: str) -> Union[str, None]:
        raise NotImplementedError()

    async def get_owner_wait_target(self, owner_id: str) -> Union[str, None]:
        raise NotImplementedError()

    async def track_wait_target(self, lock_id: Union[str, None], owner_id: str):
        raise NotImplementedError()

    async def clear_wait_target(self, owner_id: str):
        raise NotImplementedError()

    async def is_locked(self, lock_id: str) -> bool:
        raise NotImplementedError()

    async def get_lock_count(
        self,
    ) -> int:
        raise NotImplementedError()

    async def acquire(
        self,
        lock_id: str,
        owner_id: Optional[str] = None,
        timeout: Union[int, float, None] = None,
        lock_timeout: Union[int, float, None] = None,
    ) -> bool:
        raise NotImplementedError()

    async def releases(self, lock_id: str, owner_id: Optional[str] = None) -> bool:
        raise NotImplementedError()

    # observables
    async def create_observable(self, type: str, *args, **kwargs) -> Observable:
        raise NotImplementedError()

    # processing
    async def process_analysis_request(self, ar: AnalysisRequest):
        raise NotImplementedError()

    # storage
    async def store_content(self, content: Union[bytes, str, io.IOBase], meta: ContentMetadata) -> str:
        raise NotImplementedError()

    async def get_content_bytes(self, sha256: str) -> Union[bytes, None]:
        raise NotImplementedError()

    async def get_content_stream(self, sha256: str) -> Union[io.IOBase, None]:
        raise NotImplementedError()

    async def get_content_meta(self, sha256: str) -> Union[ContentMetadata, None]:
        raise NotImplementedError()

    async def delete_content(self, sha256: str) -> bool:
        raise NotImplementedError()

    async def track_content_root(self, sha256: str, root: Union[RootAnalysis, str]):
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
        self, owner_uuid: str, amt: Union[AnalysisModuleType, str], timeout: Optional[int] = 0
    ) -> Union[AnalysisRequest, None]:
        raise NotImplementedError()
