# vim: ts=4:sw=4:et:cc=120

import datetime
import json
import logging
import threading

from operator import itemgetter
from typing import Optional, List, Union

from ace.json import JSONEncoder
from ace.analysis import Observable
from ace.system.constants import *
from ace.system.analysis_request import AnalysisRequestTrackingInterface, AnalysisRequest
from ace.system.analysis_module import AnalysisModuleType
from ace.system.caching import generate_cache_key


class ThreadedAnalysisRequestTrackingInterface(AnalysisRequestTrackingInterface):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # we have different ways to tracking the requests
        # track by AnalysisRequest.id
        self.analysis_requests = {}  # key = AnalysisRequest.id, value = AnalysisRequest

        # linked requests
        self.links = {}  # key = source AnalysisRequest.id, value = set(dest AnalysisRequest.id)

        # track by the cache index, if it exists
        self.cache_index = {}  # key = generate_cache_key(observable, amt), value = AnalysisRequest

        # track by root
        self.root_index = {}  # key = RootAnalysis.uuid, value = set(AnalysisRequest)

        # expiration tracking
        self.expiration_tracking = {}  # key = request.id, value = of (datetime, request)

        # sync changes to any of these tracking dicts
        self.sync_lock = threading.RLock()

    def track_analysis_request(self, request: AnalysisRequest):
        with self.sync_lock:
            json_data = json.dumps(request.to_dict(), cls=JSONEncoder, sort_keys=True)
            # are we already tracking this?
            existing_analysis_request = self.get_analysis_request_by_request_id(request.id)
            self.analysis_requests[request.id] = json_data
            if existing_analysis_request and existing_analysis_request.cache_key:
                # did the cache key change?
                if existing_analysis_request.cache_key != request.cache_key:
                    try:
                        del self.cache_index[request.cache_key]
                    except KeyError:
                        pass

            # update lookup by cache key
            if request.cache_key:
                self.cache_index[request.cache_key] = json_data

            # update root lookup index
            if request.root.uuid not in self.root_index:
                self.root_index[request.root.uuid] = set()

            self.root_index[request.root.uuid].add(request.id)

            if request.type:
                # if we've started analyzing this request then we start tracking expiration of the request
                if request.status == TRACKING_STATUS_ANALYZING:
                    self._track_request_expiration(request)
                else:
                    # if the status is anything but ANALYZING then we STOP tracking the expiration
                    self._delete_request_expiration(request)

    def link_analysis_requests(self, source: AnalysisRequest, dest: AnalysisRequest):
        with self.sync_lock:
            if source.id not in self.links:
                self.links[source.id] = set()

            self.links[source.id].add(dest.id)

    def get_linked_analysis_requests(self, source: AnalysisRequest) -> list[AnalysisRequest]:
        with self.sync_lock:
            return [self.get_analysis_request_by_request_id(_) for _ in self.links.get(source.id, [])]

    def _track_request_expiration(self, request: AnalysisRequest):
        """Utility function that implements the tracking of the expiration of the request."""
        json_data = json.dumps(request.to_dict(), cls=JSONEncoder, sort_keys=True)
        # are we already tracking this?
        if request.id not in self.expiration_tracking:
            self.expiration_tracking[request.id] = (
                datetime.datetime.now() + datetime.timedelta(seconds=request.type.timeout),
                json_data,
            )

    def _delete_request_expiration(self, request: AnalysisRequest) -> bool:
        """Utility function that implements the deletion of the tracking of the expiration of the request."""
        try:
            del self.expiration_tracking[request.id]
            return True
        except KeyError:
            return False

    def delete_analysis_request(self, key: str) -> bool:
        with self.sync_lock:
            # does it even exist?
            json_data = self.analysis_requests.pop(key, None)
            if json_data is None:
                logging.debug(f"analysis request {key} does not exist")
                return False

            request = AnalysisRequest.from_dict(json.loads(json_data))

            # also delete from the cache lookup if it's in there
            if request.cache_key:
                logging.debug(f"analysis request {key} deleted from cache with key {request.cache_key}")
                self.cache_index.pop(request.cache_key, None)

            # update the root lookup index
            try:
                self.root_index[request.root.uuid].remove(request.id)
            except KeyError:
                pass

            # clear the root lookup index if this is the last request
            if not self.root_index[request.root.uuid]:
                del self.root_index[request.root.uuid]

            # clear any links
            self.links.pop(request.id, None)

            # and finally delete any expiration tracking if it exists
            if request.type:
                self._delete_request_expiration(request)

            logging.debug(f"deleted {request}")
            return True

    def get_expired_analysis_requests(self) -> list[AnalysisRequest]:
        result = []
        with self.sync_lock:
            try:
                # XXX super inefficient but who cares right now
                for tracking_id, (expiration_time, request) in self.expiration_tracking.items():
                    # is it past expiration time for this request
                    if datetime.datetime.now() >= expiration_time:
                        result.append(request)
            except KeyError:
                return []

        return [AnalysisRequest.from_dict(json.loads(_)) for _ in result]

    # this is called when an analysis module type is removed (or expired)
    def clear_tracking_by_analysis_module_type(self, amt: AnalysisModuleType):
        with self.sync_lock:
            target_list = []  # the list of request.id that we need to get rid of
            for request_id, json_data in self.request_tracking.items():
                request = AnalysisRequest.from_dict(json.loads(json_data))
                if request.type.name == amt.name:
                    target_list.append(request_id)

            for request_id in target_list:
                self.delete_analysis_request(request_id)

            # also delete the entire dict for the analysis module type
            if amt.name in self.amt_exp_tracking:
                del self.amt_exp_tracking[amt.name]

    def get_analysis_request_by_request_id(self, key: str) -> Union[AnalysisRequest, None]:
        with self.sync_lock:
            json_data = self.analysis_requests.get(key)

        if json_data is None:
            return None

        return AnalysisRequest.from_dict(json.loads(json_data))


    def get_analysis_request_by_cache_key(self, key: str) -> Union[AnalysisRequest, None]:
        with self.sync_lock:
            json_data = self.cache_index.get(key)

        if json_data is None:
            return None

        return AnalysisRequest.from_dict(json.loads(json_data))

    def get_analysis_requests_by_root(self, key: str) -> list[AnalysisRequest]:
        with self.sync_lock:
            return [self.get_analysis_request_by_request_id(_) for _ in self.root_index.get(key, set())]

    def reset(self):
        self.analysis_requests = {}
        self.cache_index = {}
        self.expiration_tracking = {}
