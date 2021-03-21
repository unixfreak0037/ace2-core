# vim: ts=4:sw=4:et:cc=120
#

import contextlib
import io
import json
import os.path

from typing import Union, Any, Optional, AsyncGenerator

import ace.data_model

from ace.data_model import (
    AlertListModel,
    AnalysisRequestQueryModel,
    ConfigurationSetting,
    ContentMetadata,
    CustomJSONEncoder,
    ErrorModel,
    Event,
)
from ace.analysis import RootAnalysis, AnalysisModuleType, Observable
from ace.api.base import AceAPI
from ace.system.analysis_request import AnalysisRequest
from ace.system.constants import ERROR_AMT_VERSION, ERROR_AMT_EXTENDED_VERSION, ERROR_AMT_DEP
from ace.system.events import EventHandler
from ace.system.exceptions import (
    AnalysisModuleTypeDependencyError,
    exception_map,
    AnalysisModuleTypeVersionError,
    AnalysisModuleTypeExtendedVersionError,
    DuplicateApiKeyNameError,
)

import aiofiles

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

    api_key = None

    def get_client(self):
        kwargs = {}
        kwargs.update(self.client_kwargs)
        if "headers" not in kwargs:
            kwargs["headers"] = {}

        kwargs["headers"].update({"X-API-Key": self.api_key})
        return AsyncClient(*self.client_args, **kwargs)

    # alerting
    async def register_alert_system(self, name: str) -> bool:
        assert isinstance(name, str) and name
        async with self.get_client() as client:
            response = await client.put(f"/ams/{name}")

        _raise_exception_on_error(response)
        return response.status_code == 201

    async def unregister_alert_system(self, name: str) -> bool:
        assert isinstance(name, str) and name
        async with self.get_client() as client:
            response = await client.delete(f"/ams/{name}")

        _raise_exception_on_error(response)
        return response.status_code == 200

    async def submit_alert(self, root: Union[RootAnalysis, str]) -> bool:
        raise NotImplementedError()

    async def get_alerts(self, name: str, timeout: Optional[int] = None) -> list[str]:
        assert isinstance(name, str) and name
        assert timeout is None or isinstance(timeout, int)

        params = {}
        if timeout is not None:
            params["timeout"] = str(timeout)

        async with self.get_client() as client:
            response = await client.get(f"/ams/{name}", params=params)

        _raise_exception_on_error(response)
        return AlertListModel.parse_obj(response.json()).root_uuids

    async def get_alert_count(self, name: str) -> int:
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

    async def process_expired_analysis_requests(self, amt: AnalysisModuleType):
        raise NotImplementedError()

    # analysis tracking
    async def get_root_analysis(self, root: Union[RootAnalysis, str]) -> Union[RootAnalysis, None]:
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
        assert isinstance(key, str) and key

        async with self.get_client() as client:
            response = await client.get(f"/config", params={"key": key})

        _raise_exception_on_error(response)
        if response.status_code == 404:
            return None

        return ConfigurationSetting(**response.json())

    async def set_config(self, key: str, value: Any, documentation: Optional[str] = None):
        async with self.get_client() as client:
            response = await client.put(
                f"/config", json=ConfigurationSetting(name=key, value=value, documentation=documentation).dict()
            )

        _raise_exception_on_error(response)
        if response.status_code == 401:
            return True

        return False

    async def delete_config(self, key: str) -> bool:
        assert isinstance(key, str) and key

        async with self.get_client() as client:
            response = await client.delete(f"/config", params={"key": key})

        _raise_exception_on_error(response)
        if response.status_code == 200:
            return True
        elif response.status_code == 404:
            return False
        else:
            raise RuntimeError(f"unexpected status code {response.status_code}")

    # events
    async def register_event_handler(self, event: str, handler: EventHandler):
        raise NotImplementedError()

    async def remove_event_handler(self, handler: EventHandler, events: Optional[list[str]] = []):
        raise NotImplementedError()

    async def get_event_handlers(self, event: str) -> list[EventHandler]:
        raise NotImplementedError()

    async def fire_event(self, event: Event):
        raise NotImplementedError()

    # observables
    async def create_observable(self, type: str, *args, **kwargs) -> Observable:
        raise NotImplementedError()

    # processing
    async def process_analysis_request(self, ar: AnalysisRequest):
        async with self.get_client() as client:
            response = await client.post("/process_request", json=ar.to_dict())

        _raise_exception_on_error(response)

    # storage
    async def store_content(self, content: Union[bytes, str, io.IOBase], meta: ContentMetadata) -> str:
        if isinstance(content, str):
            content = io.BytesIO(content.encode())
        elif isinstance(content, bytes):
            content = io.BytesIO(content)

        files = {"file": content}
        data = {"name": meta.name}

        if meta.expiration_date:
            data["expiration_date"] = meta.expiration_date.isoformat()

        if meta.custom:
            data["custom"] = json.dumps(meta.custom, cls=CustomJSONEncoder)

        async with self.get_client() as client:
            response = await client.post("/storage", files=files, data=data)

        _raise_exception_on_error(response)
        return ContentMetadata(**response.json()).sha256

    async def get_content_bytes(self, sha256: str) -> Union[bytes, None]:
        async with self.get_client() as client:
            async with client.stream("GET", f"/storage/{sha256}") as response:
                _raise_exception_on_error(response)
                if response.status_code == 404:
                    return None

                return await response.aread()

    async def iter_content(self, sha256: str, buffer_size: int) -> Union[AsyncGenerator[bytes, None], None]:
        async with self.get_client() as client:
            async with client.stream("GET", f"/storage/{sha256}") as response:
                _raise_exception_on_error(response)
                if response.status_code == 404:
                    yield None
                    return

                async for data in response.aiter_bytes():
                    yield data

    async def get_content_meta(self, sha256: str) -> Union[ContentMetadata, None]:
        async with self.get_client() as client:
            response = await client.get(f"/storage/meta/{sha256}")

        _raise_exception_on_error(response)
        if response.status_code == 404:
            return None

        return ContentMetadata(**response.json())

    async def delete_content(self, sha256: str) -> bool:
        raise NotImplementedError()

    async def track_content_root(self, sha256: str, root: Union[RootAnalysis, str]):
        raise NotImplementedError()

    async def save_file(self, path: str, **kwargs) -> Union[str, None]:
        meta = ContentMetadata(name=os.path.basename(path), **kwargs)
        with open(path, "rb") as fp:
            return await self.store_content(fp, meta)

    async def load_file(self, sha256: str, path: str) -> Union[ContentMetadata, None]:
        meta = await self.get_content_meta(sha256)
        if meta is None:
            return None

        async with aiofiles.open(path, "wb") as fp:
            async with self.get_client() as client:
                async with client.stream("GET", f"/storage/{sha256}") as response:
                    _raise_exception_on_error(response)
                    async for chunk in response.aiter_bytes():
                        await fp.write(chunk)

        return meta

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
            version = amt.version
            extended_version = amt.extended_version
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
            return AnalysisRequest.from_dict(response.json(), self.system)

    #
    # authentication
    #

    async def create_api_key(
        self, name: str, description: Optional[str] = None, is_admin: Optional[bool] = False
    ) -> str:
        async with self.get_client() as client:
            data = {"name": name, "is_admin": is_admin}
            if description is not None:
                data["description"] = description

            response = await client.post(
                "/auth",
                data=data,
            )

        _raise_exception_on_error(response)

        if response.status_code == 200:
            raise DuplicateApiKeyNameError()

        return ace.data_model.ApiKeyResponseModel(**response.json()).api_key

    async def delete_api_key(self, name: str) -> bool:
        async with self.get_client() as client:
            response = await client.delete(f"/auth/{name}")

        _raise_exception_on_error(response)

        if response.status_code == 200:
            return True
        else:
            return False

    async def verify_api_key(self, api_key: str, is_admin: Optional[bool] = False) -> bool:
        raise NotImplementedError()
