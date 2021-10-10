# vim: ts=4:sw=4:et:cc=120
#

#
# utility system definitions for testing
#

import os
import os.path
import tempfile
import shutil

from typing import Optional, Union, Any, Iterator

from ace.analysis import RootAnalysis, AnalysisModuleType, Observable
from ace.api import AceAPI
from ace.api.remote import RemoteAceAPI
from ace.crypto import initialize_encryption_settings, EncryptionSettings
from ace.data_model import ContentMetadata
from ace.logging import get_logger
from ace.system.database import DatabaseACESystem
from ace.system.distributed import app
from ace.system.events import EventHandler
from ace.system.redis import RedisACESystem
from ace.system.remote import RemoteACESystem
from ace.system.requests import AnalysisRequest
from ace.system.threaded import ThreadedACESystem

from httpx import AsyncClient
import redislite
from sqlalchemy import event


class ThreadedACETestSystem(ThreadedACESystem):
    pass


class DatabaseACETestSystem(DatabaseACESystem, ThreadedACESystem):

    # running the tests in memory works as long as the same db connection is
    # always used

    # db_url = "sqlite:///ace.db"
    # db_url = "sqlite+aiosqlite://"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, storage_root=tempfile.mkdtemp())
        self.db_url = "sqlite+aiosqlite://"

    async def initialize(self):
        await super().initialize()

        @event.listens_for(self.engine.sync_engine, "engine_connect")
        def connect(dbapi_connection, connection_record):
            cursor = dbapi_connection.connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    async def reset(self):
        result = await super().reset()

        self.engine = None

        # remove the temporary file we used
        if os.path.exists("ace.db"):
            os.remove("ace.db")

        # re-initialize and create the database
        await self.initialize()
        await self.create_database()

        # reset the storage_root
        shutil.rmtree(self.storage_root)
        self.storage_root = tempfile.mkdtemp()

    async def create_database(self):
        from ace.system.database.schema import Base

        get_logger().info(f"creating database {self.db_url}")
        Base.metadata.bind = self.engine
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def stop(self):
        await super().stop()

        if os.path.exists("ace.db"):
            os.remove("ace.db")


class RedisACETestSystem(RedisACESystem, DatabaseACETestSystem, ThreadedACESystem):
    async def reset(self):
        await super().reset()

        # clear everything
        async with self.get_redis_connection() as rc:
            await rc.flushall()

    async def stop(self):
        await self.close_redis_connections()
        # async with self.get_redis_connection() as rc:
        # rc.close()
        # await rc.wait_closed()


class DistributedACETestSystem(RedisACETestSystem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db_url = "sqlite+aiosqlite:///ace_distributed.db"

    async def reset(self):
        if os.path.exists("ace_distributed.db"):
            os.remove("ace_distributed.db")

        await super().reset()


class RemoteACETestSystem(RemoteACESystem):
    def __init__(self, api_key: str):
        super().__init__("http://test", api_key, client_args=[], client_kwargs={"app": app})

    # the remote API only supports a handful of the calls
    # so for the rest of them we directly call using the Fast API app reference

    # alerting

    async def submit_alert(self, root: Union[RootAnalysis, str]) -> bool:
        return await app.state.system.submit_alert(root)

    async def get_alert_count(self, name: str) -> int:
        return await app.state.system.get_alert_count(name)

    # events

    async def register_event_handler(self, event: str, handler: EventHandler):
        return await app.state.system.register_event_handler(event, handler)

    async def remove_event_handler(self, handler: EventHandler, events: Optional[list[str]] = []):
        return await app.state.system.remove_event_handler(handler, events)

    async def get_event_handlers(self, event: str) -> list[EventHandler]:
        return await app.state.system.get_event_handlers(event)

    async def fire_event(self, event: str, event_args: Optional[Any] = None):
        return await app.state.system.fire_event(event, event_args)

    # analysis module

    async def track_analysis_module_type(self, amt: AnalysisModuleType):
        return await app.state.system.track_analysis_module_type(amt)

    async def delete_analysis_module_type(self, amt: Union[AnalysisModuleType, str]) -> bool:
        return await app.state.system.delete_analysis_module_type(amt)

    async def get_all_analysis_module_types(self) -> list[AnalysisModuleType]:
        return await app.state.system.get_all_analysis_module_types()

    # work queue

    async def delete_work_queue(self, amt: Union[AnalysisModuleType, str]) -> bool:
        return await app.state.system.delete_work_queue(amt)

    async def add_work_queue(self, amt: Union[AnalysisModuleType, str]) -> bool:
        return await app.state.system.add_work_queue(amt)

    async def put_work(self, amt: Union[AnalysisModuleType, str], analysis_request: AnalysisRequest):
        return await app.state.system.put_work(amt)

    async def get_work(self, amt: Union[AnalysisModuleType, str], timeout: int) -> Union[AnalysisRequest, None]:
        return await app.state.system.get_work(amt, timeout)

    async def get_queue_size(self, amt: Union[AnalysisModuleType, str]) -> int:
        return await app.state.system.get_queue_size(amt)

    # analysis tracking

    async def track_root_analysis(self, root: RootAnalysis) -> bool:
        return await app.state.system.track_root_analysis(root)

    async def update_root_analysis(self, root: RootAnalysis) -> bool:
        return await app.state.system.update_root_analysis(root)

    async def delete_root_analysis(self, root: Union[RootAnalysis, str]) -> bool:
        return await app.state.system.delete_root_analysis(root)

    async def root_analysis_exists(self, root: Union[RootAnalysis, str]) -> bool:
        return await app.state.system.root_analysis_exists(root)

    async def track_analysis_details(self, root: RootAnalysis, uuid: str, value: Any) -> bool:
        return await app.state.system.track_analysis_details(root, uuid, value)

    async def delete_analysis_details(self, uuid: str) -> bool:
        return await app.state.system.delete_analysis_details(uuid)

    async def analysis_details_exists(self, uuid: str) -> bool:
        return await app.state.system.delete_analysis_details(uuid)

    # request tracking

    async def track_analysis_request(self, request: AnalysisRequest):
        return await app.state.system.track_analysis_request(request)

    async def lock_analysis_request(self, request: AnalysisRequest) -> bool:
        return await app.state.system.lock_analysis_request(request)

    async def unlock_analysis_request(self, request: AnalysisRequest) -> bool:
        return await app.state.system.unlock_analysis_request(request)

    async def link_analysis_requests(self, source_request: AnalysisRequest, dest_request: AnalysisRequest) -> bool:
        return await app.state.system.link_analysis_requests(source_request, dest_request)

    async def get_linked_analysis_requests(self, source_request: AnalysisRequest) -> list[AnalysisRequest]:
        return await app.state.system.get_linked_analysis_requests(source_request)

    async def delete_analysis_request(self, target: Union[AnalysisRequest, str]) -> bool:
        return await app.state.system.delete_analysis_request(target)

    async def get_expired_analysis_requests(self) -> list[AnalysisRequest]:
        return await app.state.system.get_expired_analysis_requests()

    async def get_analysis_request(self, key: str) -> Union[AnalysisRequest, None]:
        return await app.state.system.get_analysis_request(key)

    async def get_analysis_request_by_request_id(self, request_id: str) -> Union[AnalysisRequest, None]:
        return await app.state.system.get_analysis_request_by_request_id(request_id)

    async def get_analysis_request_by_observable(
        self, observable: Observable, amt: AnalysisModuleType
    ) -> Union[AnalysisRequest, None]:
        return await app.state.system.get_analysis_request_by_observable(observable, amt)

    async def get_analysis_requests_by_root(self, key: str) -> list[AnalysisRequest]:
        return await app.state.system.get_analysis_requests_by_root(key)

    async def clear_tracking_by_analysis_module_type(self, amt: AnalysisModuleType):
        return await app.state.system.clear_tracking_by_analysis_module_type(amt)

    async def process_expired_analysis_requests(self, amt: AnalysisModuleType):
        return await app.state.system.process_expired_analysis_requests(amt)

    async def queue_analysis_request(self, ar: AnalysisRequest):
        return await app.state.system.queue_analysis_request(ar)

    # storage

    async def iter_expired_content(self) -> Iterator[ContentMetadata]:
        return await app.state.system.iter_expired_content()

    async def delete_content(self, sha256: str) -> bool:
        return await app.state.system.delete_content(sha256)

    async def track_content_root(self, sha256: str, root: Union[RootAnalysis, str]):
        return await app.state.system.track_content_root(sha256, root)

    async def has_valid_root_reference(self, meta: ContentMetadata) -> bool:
        return await app.state.system.has_valid_root_reference(meta)

    async def delete_expired_content(self) -> int:
        return await app.state.system.delete_expired_content()

    # caching

    async def get_cached_analysis_result(
        self, observable: Observable, amt: AnalysisModuleType
    ) -> Union[AnalysisRequest, None]:
        return await app.state.system.get_cached_analysis_result(observable, amt)

    async def cache_analysis_result(self, request: AnalysisRequest) -> Union[str, None]:
        return await app.state.system.cache_analysis_result(request)

    async def delete_expired_cached_analysis_results(self):
        return await app.state.system.delete_expired_cached_analysis_results()

    async def delete_cached_analysis_results_by_module_type(self, amt: AnalysisModuleType):
        return await app.state.system.delete_cached_analysis_results_by_module_type(amt)

    async def get_cache_size(self, amt: Optional[AnalysisModuleType] = None):
        return await app.state.system.get_cache_size(amt)


class RemoteACETestSystemProcess(RemoteACESystem):
    def __init__(self, redis_url: str, api_key: str, encryption_settings: EncryptionSettings, *args, **kwargs):
        super().__init__("http://test", api_key, client_args=[], client_kwargs={"app": app}, *args, **kwargs)
        self.redis_url = redis_url
        self.api.api_key = api_key
        self.existing_encryption_settings = encryption_settings

    async def initialize(self):
        await super().initialize()

        print("*** initializing app.state.system ***")

        # configure the distributed system that sits behind the fake FastAPI
        app.state.system = DistributedACETestSystem()
        from ace.system.redis import CONFIG_REDIS_HOST, CONFIG_REDIS_PORT

        # pull the unix path from the redislist connection pool
        await app.state.system.set_config(CONFIG_REDIS_HOST, self.redis_url)

        #
        # NOTE app.state.system is actually already set up by RemoteACETestSystem
        # so all we need to do is to use the existing settings passed in on the constructor
        #

        app.state.system.encryption_settings = self.existing_encryption_settings
        app.state.system.encryption_settings.load_aes_key("test")
        app.state.system.root_api_key = self.api.api_key

        await app.state.system.initialize()

        print("*** app.state.system initialized OK ***")
