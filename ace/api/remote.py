# vim: ts=4:sw=4:et:cc=120
#

import io

from contextlib import contextmanager
from typing import Union, Any, Optional

from ace.data_model import AnalysisRequestQueryModel, ErrorModel
from ace.analysis import RootAnalysis, AnalysisModuleType, Observable
from ace.api.base import AceAPI
from ace.system.analysis_request import AnalysisRequest
from ace.system.constants import ERROR_AMT_VERSION, ERROR_AMT_EXTENDED_VERSION, ERROR_AMT_DEP
from ace.system.events import EventHandler
from ace.system.exceptions import AnalysisModuleTypeDependencyError, exception_map
from ace.system.storage import ContentMetadata
from ace.system.work_queue import AnalysisModuleTypeVersionError, AnalysisModuleTypeExtendedVersionError

from httpx import AsyncClient

# maps error codes to exceptions


def _raise_exception_on_error(response):
    if response.status_code == 400:
        _raise_exception_from_error_model(ErrorModel.parse_obj(response.json()))


def _raise_exception_from_error_model(error: ErrorModel):
    """Raises an exception based on the code of the error.
    If the error code is unknown then a generic RuntimeError is raised."""
    if error.code in exception_map:
        raise exception_map[error.code](error.details)
    else:
        raise RuntimeError(f"unknown error code {error.code}: {error.details}")


class RemoteAceAPI(AceAPI):
    def get_client(self):
        return AsyncClient(*self.client_args, **self.client_kwargs)

    # alerting
    async def track_alert(self, root: RootAnalysis):
        raise NotImplementedError()

    # analysis module
    async def register_analysis_module_type(self, amt: AnalysisModuleType) -> AnalysisModuleType:
        assert isinstance(amt, AnalysisModuleType)
        async with self.get_client() as client:
            response = await client.post("/amt", json=amt.to_dict())

        _raise_exception_on_error(response)
        return AnalysisModuleType.from_dict(response.json())

    async def track_analysis_module_type(self, amt: AnalysisModuleType):
        raise NotImplementedError()

    async def get_analysis_module_type(self, name: str) -> Union[AnalysisModuleType, None]:
        assert isinstance(name, str) and name
        async with self.get_client() as client:
            response = await client.get(f"/amt/{name}")

        _raise_exception_on_error(response)
        if response.status_code == 404:
            return None

        return AnalysisModuleType.from_dict(response.json())

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
        assert isinstance(ar, AnalysisRequest)

        async with self.get_client() as client:
            response = await client.post("/process_request", json=ar.to_dict())

        _raise_exception_on_error(response)

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

    async def store_file(self, path: str, **kwargs) -> str:
        """Utility function that stores the contents of the given file and returns the sha256 hash."""
        assert isinstance(path, str)
        meta = ContentMetadata(path, **kwargs)
        with open(path, "rb") as fp:
            return store_content(fp, meta)

    async def get_file(self, sha256: str, path: Optional[str] = None) -> bool:
        """Utility function that pulls data out of storage into a local file. The
        original path is used unless a target path is specified."""
        assert isinstance(sha256, str)
        assert path is None or isinstance(path, str)

        meta = get_content_meta(sha256)
        if meta is None:
            return False

        if path is None:
            path = meta.name

        with open(path, "wb") as fp_out:
            with contextlib.closing(get_content_stream(sha256)) as fp_in:
                shutil.copyfileobj(fp_in, fp_out)

        return True

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
        if isinstance(amt, AnalysisModuleType):
            amt = amt.name

        async with self.get_client() as client:
            response = await client.post(
                "/work_queue",
                json=AnalysisRequestQueryModel(
                    owner=owner_uuid,
                    amt=amt,
                    timeout=timeout,
                    version=version,
                    extended_version=extended_version,
                ).dict(),
            )

        _raise_exception_on_error(response)

        if response.status_code == 204:
            return None
        else:
            return AnalysisRequest.from_dict(response.json())