# vim: ts=4:sw=4:et:cc=120
#
# global system components

from typing import Union, Optional, Any, Iterator, AsyncGenerator

import contextlib
import functools
import inspect
import io
import logging
import os
import types


def get_logger():
    return logging.getLogger("ace")


from ace.analysis import RootAnalysis, AnalysisModuleType, Observable
from ace.crypto import EncryptionSettings, is_valid_password
from ace.system.constants import *
from ace.data_model import ConfigurationSetting, Event, ContentMetadata
from ace.system.caching import generate_cache_key
from ace.system.exceptions import (
    AnalysisModuleTypeDependencyError,
    AnalysisModuleTypeExtendedVersionError,
    AnalysisModuleTypeVersionError,
    AnalysisRequestLockedError,
    CircularDependencyError,
    ExpiredAnalysisRequestError,
    MissingEncryptionSettingsError,
    UnknownAnalysisModuleTypeError,
)
from ace.system.events import EventHandler
from ace.system.analysis_request import AnalysisRequest


def coreapi(func):
    """Specifies the given function is a core api function."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    wrapper.__coreapi__ = True
    return wrapper


class ACESystem:

    #
    # alerting
    #

    @coreapi
    async def register_alert_system(self, name: str) -> bool:
        assert isinstance(name, str) and name
        result = await self.i_register_alert_system(name)
        if result:
            await self.fire_event(EVENT_ALERT_SYSTEM_REGISTERED, name)

        return result

    async def i_register_alert_system(self, name: str) -> bool:
        raise NotImplementedError()

    @coreapi
    async def unregister_alert_system(self, name: str) -> bool:
        assert isinstance(name, str) and name
        result = await self.i_unregister_alert_system(name)
        if result:
            await self.fire_event(EVENT_ALERT_SYSTEM_UNREGISTERED, name)

        return result

    async def i_unregister_alert_system(self, name: str) -> bool:
        raise NotImplementedError()

    @coreapi
    async def submit_alert(self, root: Union[RootAnalysis, str]) -> bool:
        """Submits the given RootAnalysis uuid as an alert to any registered alert systems.
        Returns True if at least one system is registered, False otherwise."""
        assert isinstance(root, str) or isinstance(root, RootAnalysis)
        if isinstance(root, RootAnalysis):
            root = root.uuid

        get_logger().info(f"submitting alert {root}")
        result = await self.i_submit_alert(root)
        if result:
            await self.fire_event(EVENT_ALERT, root)

        return result

    async def i_submit_alert(self, root_uuid: str) -> bool:
        raise NotImplementedError()

    @coreapi
    async def get_alerts(self, name: str, timeout: Optional[int] = None) -> list[str]:
        assert isinstance(name, str) and name
        return await self.i_get_alerts(name, timeout)

    async def i_get_alerts(self, name: str, timeout: Optional[int] = None) -> list[str]:
        raise NotImplementedError()

    #
    # alerting instrumentation
    #

    @coreapi
    async def get_alert_count(self, name: str) -> int:
        """Returns the number of alerts outstanding for the given registered alert system."""
        assert isinstance(name, str) and name
        return await self.i_get_alert_count(name)

    async def i_get_alert_count(self, name: str) -> int:
        raise NotImplementedError()

    #
    # analysis tracking
    #

    @coreapi
    async def get_root_analysis(self, root: Union[RootAnalysis, str]) -> Union[RootAnalysis, None]:
        """Returns the loaded RootAnalysis for the given RootAnalysis or uuid, or None if it does not exist."""
        assert isinstance(root, RootAnalysis) or isinstance(root, str)

        if isinstance(root, RootAnalysis):
            root = root.uuid

        get_logger().debug(f"getting root analysis uuid {root}")
        result = await self.i_get_root_analysis(root)
        if result:
            result.system = self

        return result

    async def i_get_root_analysis(self, uuid: str) -> Union[RootAnalysis, None]:
        """Returns the root for the given uuid or None if it does not exist.."""
        raise NotImplementedError()

    @coreapi
    async def track_root_analysis(self, root: RootAnalysis) -> bool:
        """Inserts or updates the root analysis. Returns True if either operation is successfull."""
        assert isinstance(root, RootAnalysis)

        if root.uuid is None:
            raise ValueError(f"uuid property of {root} is None in track_root_analysis")

        get_logger().debug(f"tracking root {root}")
        if not await self.i_track_root_analysis(root):
            return await self.update_root_analysis(root)

        # make sure storage content is tracked to their roots
        for observable in root.get_observables_by_type("file"):
            await self.track_content_root(observable.value, root)

        await self.fire_event(EVENT_ANALYSIS_ROOT_NEW, root)
        return True

    async def i_track_root_analysis(self, root: RootAnalysis) -> bool:
        """Tracks the root analysis, returns True if it worked. Updates the
        version property of the root."""
        raise NotImplementedError()

    @coreapi
    async def update_root_analysis(self, root: RootAnalysis) -> bool:
        assert isinstance(root, RootAnalysis)

        if root.uuid is None:
            raise ValueError(f"uuid property of {root} is None in update_root_analysis")

        get_logger().debug(f"updating root {root} with version {root.version}")
        if not await self.i_update_root_analysis(root):
            return False

        # make sure storage content is tracked to their roots
        for observable in root.get_observables_by_type("file"):
            await self.track_content_root(observable.value, root)

        await self.fire_event(EVENT_ANALYSIS_ROOT_MODIFIED, root)
        return True

    async def i_update_root_analysis(self, root: RootAnalysis) -> bool:
        """Updates the root. Returns True if the update was successful, False
        otherwise. Updates the version property of the root.

        The version of the root passed in must match the version on record for
        the update to work."""
        raise NotImplementedError()

    @coreapi
    async def delete_root_analysis(self, root: Union[RootAnalysis, str]) -> bool:
        assert isinstance(root, RootAnalysis) or isinstance(root, str)

        if isinstance(root, RootAnalysis):
            root = root.uuid

        get_logger().debug(f"deleting root {root}")
        result = await self.i_delete_root_analysis(root)
        if result:
            await self.fire_event(EVENT_ANALYSIS_ROOT_DELETED, root)

        return result

    async def i_delete_root_analysis(self, uuid: str) -> bool:
        """Deletes the given RootAnalysis JSON data by uuid, and any associated analysis details."""
        raise NotImplementedError()

    @coreapi
    async def root_analysis_exists(self, root: Union[RootAnalysis, str]) -> bool:
        assert isinstance(root, RootAnalysis) or isinstance(root, str)

        if isinstance(root, RootAnalysis):
            root = root.uuid

        return await self.i_root_analysis_exists(root)

    async def i_root_analysis_exists(self, uuid: str) -> bool:
        """Returns True if the given root analysis exists, False otherwise."""
        raise NotImplementedError()

    @coreapi
    async def get_analysis_details(self, uuid: str) -> Any:
        assert isinstance(uuid, str)

        return await self.i_get_analysis_details(uuid)

    async def i_get_analysis_details(self, uuid: str) -> Any:
        """Returns the details for the given Analysis object, or None if is has not been set."""
        raise NotImplementedError()

    @coreapi
    async def track_analysis_details(self, root: RootAnalysis, uuid: str, value: Any) -> bool:
        assert isinstance(root, RootAnalysis)
        assert isinstance(uuid, str)

        # we don't save Analysis that doesn't have the details set
        if value is None:
            return False

        get_logger().debug(f"tracking {root} analysis details {uuid}")
        exists = await self.analysis_details_exists(root.uuid)
        await self.i_track_analysis_details(root.uuid, uuid, value)
        if not exists:
            await self.fire_event(EVENT_ANALYSIS_DETAILS_NEW, [root, root.uuid])
        else:
            await self.fire_event(EVENT_ANALYSIS_DETAILS_MODIFIED, [root, root.uuid])

        return True

    async def i_track_analysis_details(self, root_uuid: str, uuid: str, value: Any):
        """Tracks the details for the given Analysis object (uuid) in the given root (root_uuid)."""
        raise NotImplementedError()

    @coreapi
    async def delete_analysis_details(self, uuid: str) -> bool:
        assert isinstance(uuid, str)

        get_logger().debug(f"deleting analysis detials {uuid}")
        result = await self.i_delete_analysis_details(uuid)
        if result:
            await self.fire_event(EVENT_ANALYSIS_DETAILS_DELETED, uuid)

        return result

    async def i_delete_analysis_details(self, uuid: str) -> bool:
        """Deletes the analysis details for the given Analysis referenced by id."""
        raise NotImplementedError()

    @coreapi
    async def analysis_details_exists(self, uuid: str) -> bool:
        assert isinstance(uuid, str)
        return await self.i_analysis_details_exists(uuid)

    async def i_analysis_details_exists(self, uuid: str) -> bool:
        """Returns True if the given analysis details exist, False otherwise."""
        raise NotImplementedError()

    #
    # analysis module tracking
    #

    @coreapi
    async def register_analysis_module_type(self, amt: AnalysisModuleType) -> AnalysisModuleType:
        """Registers the given AnalysisModuleType with the system."""

        # make sure all the dependencies exist
        for dep in amt.dependencies:
            if await self.get_analysis_module_type(dep) is None:
                raise AnalysisModuleTypeDependencyError(f"unknown type {dep}")

        # make sure there are no circular (or self) dependencies
        await self._circ_dep_check(amt)

        current_type = await self.get_analysis_module_type(amt.name)
        if current_type is None:
            await self.add_work_queue(amt.name)

        # regardless we take this to be the new registration for this analysis module
        # any updates to version or cache keys would be saved here
        await self.track_analysis_module_type(amt)

        if current_type and not current_type.version_matches(amt):
            await self.fire_event(EVENT_AMT_MODIFIED, amt)
        elif current_type is None:
            await self.fire_event(EVENT_AMT_NEW, amt)

        return amt

    @coreapi
    async def track_analysis_module_type(self, amt: AnalysisModuleType):
        assert isinstance(amt, AnalysisModuleType)
        get_logger().debug(f"tracking analysis module type {amt}")
        return await self.i_track_analysis_module_type(amt)

    async def i_track_analysis_module_type(self, amt: AnalysisModuleType):
        raise NotImplementedError()

    @coreapi
    async def delete_analysis_module_type(self, amt: Union[AnalysisModuleType, str]) -> bool:
        """Deletes (unregisters) the given AnalysisModuleType from the system.
        Any outstanding requests for this type are discarded.
        Returns True if the analysis module type was deleted, False otherwise.
        If the type does not exist then False is returned."""

        if isinstance(amt, str):
            amt = await self.get_analysis_module_type(amt)

        if not await self.get_analysis_module_type(amt.name):
            return False

        get_logger().info(f"deleting analysis module type {amt}")

        # remove the work queue for the module
        await self.delete_work_queue(amt.name)
        # remove the module
        await self.i_delete_analysis_module_type(amt)
        # remove any outstanding requests from tracking
        await self.clear_tracking_by_analysis_module_type(amt)
        # remove any cached analysis results for this type
        await self.delete_cached_analysis_results_by_module_type(amt)

        await self.fire_event(EVENT_AMT_DELETED, amt)
        return True

    async def i_delete_analysis_module_type(self, name: str):
        raise NotImplementedError()

    @coreapi
    async def get_analysis_module_type(self, name: str) -> Union[AnalysisModuleType, None]:
        """Returns the registered AnalysisModuleType by name, or None if it has not been or is no longer registered."""
        assert isinstance(name, str)
        return await self.i_get_analysis_module_type(name)

    async def i_get_analysis_module_type(self, name: str) -> Union[AnalysisModuleType, None]:
        raise NotImplementedError()

    @coreapi
    async def get_all_analysis_module_types(self) -> list[AnalysisModuleType]:
        """Returns the full list of all registered analysis module types."""
        return await self.i_get_all_analysis_module_types()

    async def i_get_all_analysis_module_types(self) -> list[AnalysisModuleType]:
        raise NotImplementedError()

    async def _circ_dep_check(
        self,
        source_amt: AnalysisModuleType,
        target_amt: Optional[AnalysisModuleType] = None,
        chain: list[AnalysisModuleType] = [],
    ):
        chain = chain[:]

        if target_amt is None:
            target_amt = source_amt

        chain.append(target_amt)

        for dep in target_amt.dependencies:
            if source_amt.name == dep:
                raise CircularDependencyError(" -> ".join([_.name for _ in chain]))

            await self._circ_dep_check(source_amt, await self.get_analysis_module_type(dep), chain)

    #
    # analysis request tracking
    #

    @coreapi
    async def track_analysis_request(self, request: AnalysisRequest):
        """Begins tracking the given AnalysisRequest."""
        assert isinstance(request, AnalysisRequest)

        if request.type and await self.get_analysis_module_type(request.type.name) is None:
            raise UnknownAnalysisModuleTypeError()

        get_logger().debug(f"tracking analysis request {request}")
        result = await self.i_track_analysis_request(request)
        await self.fire_event(EVENT_AR_NEW, request)
        return result

    async def i_track_analysis_request(self, request: AnalysisRequest):
        raise NotImplementedError()

    @coreapi
    async def lock_analysis_request(self, request: AnalysisRequest) -> bool:
        """Attempts to lock the request. Returns True if successful, False otherwise.
        A request that is locked should not be modified by a process that did not acquire the lock."""
        assert isinstance(request, AnalysisRequest)
        return await self.i_lock_analysis_request(request)

    async def i_lock_analysis_request(self, request: AnalysisRequest) -> bool:
        raise NotImplementedError()

    @coreapi
    async def unlock_analysis_request(self, request: AnalysisRequest) -> bool:
        assert isinstance(request, AnalysisRequest)
        return await self.i_unlock_analysis_request(request)

    async def i_unlock_analysis_request(self, request: AnalysisRequest) -> bool:
        raise NotImplementedError()

    @coreapi
    async def link_analysis_requests(self, source_request: AnalysisRequest, dest_request: AnalysisRequest) -> bool:
        """Links the source to the dest such that when the dest has completed,
        failed or expired, the source is then processed again."""
        assert isinstance(source_request, AnalysisRequest)
        assert isinstance(dest_request, AnalysisRequest)
        assert source_request != dest_request
        get_logger().debug(f"linking analysis request source {source_request} to dest {dest_request}")
        return await self.i_link_analysis_requests(source_request, dest_request)

    async def i_link_analysis_requests(self, source_request: AnalysisRequest, dest_request: AnalysisRequest) -> bool:
        raise NotImplementedError()

    @coreapi
    async def get_linked_analysis_requests(self, source_request: AnalysisRequest) -> list[AnalysisRequest]:
        assert isinstance(source_request, AnalysisRequest)
        return await self.i_get_linked_analysis_requests(source_request)

    async def i_get_linked_analysis_requests(self, source: AnalysisRequest) -> list[AnalysisRequest]:
        raise NotImplementedError()

    @coreapi
    async def delete_analysis_request(self, target: Union[AnalysisRequest, str]) -> bool:
        assert isinstance(target, AnalysisRequest) or isinstance(target, str)
        if isinstance(target, AnalysisRequest):
            target = target.id

        get_logger().debug(f"deleting analysis request {target}")
        result = await self.i_delete_analysis_request(target)
        if result:
            await self.fire_event(EVENT_AR_DELETED, target)

        return result

    async def i_delete_analysis_request(self, key: str) -> bool:
        raise NotImplementedError()

    @coreapi
    async def get_expired_analysis_requests(self) -> list[AnalysisRequest]:
        """Returns all AnalysisRequests that are in the TRACKING_STATUS_ANALYZING state and have expired."""
        return await self.i_get_expired_analysis_requests()

    async def i_get_expired_analysis_requests(self) -> list[AnalysisRequest]:
        raise NotImplementedError()

    @coreapi
    async def get_analysis_request(self, key: str) -> Union[AnalysisRequest, None]:
        return await self.get_analysis_request_by_request_id(key)

    @coreapi
    async def get_analysis_request_by_request_id(self, request_id: str) -> Union[AnalysisRequest, None]:
        return await self.i_get_analysis_request_by_request_id(request_id)

    async def i_get_analysis_request_by_request_id(self, key: str) -> Union[AnalysisRequest, None]:
        raise NotImplementedError()

    @coreapi
    async def get_analysis_request_by_observable(
        self, observable: Observable, amt: AnalysisModuleType
    ) -> Union[AnalysisRequest, None]:
        from ace.system.caching import generate_cache_key

        cache_key = generate_cache_key(observable, amt)
        if cache_key is None:
            return None

        return await self.i_get_analysis_request_by_cache_key(cache_key)

    async def i_get_analysis_request_by_cache_key(self, key: str) -> Union[AnalysisRequest, None]:
        raise NotImplementedError()

    @coreapi
    async def get_analysis_requests_by_root(self, key: str) -> list[AnalysisRequest]:
        """Returns all requests assigned to the given root analysis."""
        return await self.i_get_analysis_requests_by_root(key)

    async def i_get_analysis_requests_by_root(self, key: str) -> list[AnalysisRequest]:
        raise NotImplementedError()

    @coreapi
    async def clear_tracking_by_analysis_module_type(self, amt: AnalysisModuleType):
        """Deletes tracking for any requests assigned to the given analysis module type."""
        get_logger().debug(f"clearing analysis request tracking for analysis module type {amt}")
        return await self.i_clear_tracking_by_analysis_module_type(amt)

    async def i_clear_tracking_by_analysis_module_type(self, amt: AnalysisModuleType):
        raise NotImplementedError()

    @coreapi
    async def process_expired_analysis_requests(self, amt: AnalysisModuleType):
        """Moves all unlocked expired analysis requests back into the queue."""
        assert isinstance(amt, AnalysisModuleType)
        return await self.i_process_expired_analysis_requests(amt)

    async def i_process_expired_analysis_requests(self, amt: AnalysisModuleType):
        raise NotImplementedError()

    @coreapi
    async def submit_analysis_request(self, ar: AnalysisRequest):
        """Submits the given AnalysisRequest to the appropriate queue for analysis."""
        assert isinstance(ar, AnalysisRequest)
        assert isinstance(ar.root, RootAnalysis)

        ar.owner = None
        ar.status = TRACKING_STATUS_QUEUED
        await self.unlock_analysis_request(ar)
        await self.track_analysis_request(ar)

        # if this is a RootAnalysis request then we just process it here (there is no inbound queue for root analysis)
        if ar.is_root_analysis_request or ar.is_observable_analysis_result:
            return await self.process_analysis_request(ar)

        # otherwise we assign this request to the appropriate work queue based on the amt
        await self.put_work(ar.type, ar)

    @coreapi
    async def process_analysis_request(self, ar: AnalysisRequest):
        """Processes an analysis request.
        This function implements the core logic of the system."""

        get_logger().info(f"processing {ar}")
        target_root = None

        # did we complete a request?
        if ar.is_observable_analysis_result:
            existing_ar = await self.get_analysis_request(ar.id)

            # is this analysis request gone?
            if not existing_ar:
                get_logger().info(f"requested unknown analysis request {ar.id}")
                raise UnknownAnalysisRequestError(ar.id)

            # did the ownership change?
            if existing_ar.owner != ar.owner:
                get_logger().info(f"requested expired analysis request {ar.id}")
                raise ExpiredAnalysisRequestError(ar.id)

            # get the existing root analysis
            target_root = await self.get_root_analysis(ar.root)
            if not target_root:
                get_logger().info(f"analysis request {ar.id} referenced unknown root {ar.root}")
                raise UnknownRootAnalysisError(ar.id)

            # need to lock this at the beginning so that nothing else modifies it
            # while we're processing it
            # we only need to do this for observable analysis requests because they are the only types of
            # requests that can be modified (by creating linked requests)
            if not await ar.lock():
                raise AnalysisRequestLockedError(f"failed to lock analysis request {ar}")

            # should we cache these results?
            if ar.is_cachable and not ar.cache_hit:
                await self.cache_analysis_result(ar)

            # NOTE
            # when applying the diff merge it is super important to use the data from the analysis request
            # and *not* the current data

            # apply any modifications to the root
            target_root.apply_diff_merge(ar.original_root, ar.modified_root)

            # and apply any modifications to the observable
            target_observable = target_root.get_observable(ar.observable)
            if not target_observable:
                get_logger().error(f"cannot find {ar.observable} in target root {target_root}")
                raise UnknownObservableError(ar.observable)

            original_observable = ar.original_root.get_observable(ar.observable)
            if not original_observable:
                get_logger().error(f"cannot find {ar.observable} in original root {ar.original_root}")
                raise UnknownObservableError(ar.observable)

            modified_observable = ar.modified_root.get_observable(ar.observable)
            if not modified_observable:
                get_logger().error(f"cannot find {ar.observable} in modified root {ar.modified_root}")
                raise UnknownObservableError(ar.observable)

            target_observable.apply_diff_merge(original_observable, modified_observable, ar.type)
            await target_root.update_and_save()

            await self.fire_event(EVENT_PROCESSING_REQUEST_RESULT, ar)
            # TODO fire event if analysis failed

            # process any analysis request links
            for linked_request in await self.get_linked_analysis_requests(ar):
                linked_request.initialize_result()
                linked_request.original_root = ar.original_root
                linked_request.modified_root = ar.modified_root
                get_logger().debug(f"processing linked analysis request {linked_request} from {ar}")
                await self.process_analysis_request(linked_request)

        elif ar.is_root_analysis_request:
            # are we updating an existing root analysis?
            target_root = await self.get_root_analysis(ar.root)
            if target_root:
                target_root.apply_merge(ar.root)
            else:
                # otherwise we just save the new one
                target_root = ar.root

            await target_root.update_and_save()
            await self.fire_event(EVENT_PROCESSING_REQUEST_ROOT, ar)

        # this should never fire
        if target_root is None:
            get_logger().critical("hit unexpected code branch")
            raise RuntimeError("target_root is None")

        # did we generate an alert?
        if not target_root.analysis_cancelled and target_root.has_detections():
            await self.submit_alert(target_root)

        # for each observable that needs to be analyzed
        if not target_root.analysis_cancelled:
            get_logger().debug(f"processing {target_root}")
            for observable in ar.observables:
                for amt in await self.get_all_analysis_module_types():
                    # does this analysis module accept this observable?
                    if not await amt.accepts(observable, self):
                        continue

                    # is this analysis request already completed?
                    if target_root.analysis_completed(observable, amt):
                        continue

                    # is this analysis request for this RootAnalysis already being tracked?
                    if target_root.analysis_tracked(observable, amt):
                        continue

                    # is this observable being analyzed by another root analysis?
                    # NOTE if the analysis module does not support caching
                    # then get_analysis_request_by_observable always returns None
                    tracked_ar = await self.get_analysis_request_by_observable(observable, amt)

                    # at this point we know we're going to create a request to analyze this
                    new_ar = observable.create_analysis_request(amt)
                    await self.track_analysis_request(new_ar)

                    if tracked_ar and tracked_ar != ar:
                        try:
                            # tell that AR to update the details of this analysis as well when it's done
                            # if link_analysis_requests returns False it means it was unable to link it
                            if await self.link_analysis_requests(tracked_ar, new_ar):
                                observable.track_analysis_request(new_ar)
                                # track_analysis_request(new_ar)
                                await target_root.update_and_save()
                                # and then that's it for this request
                                # it waits for tracked_ar to complete
                                continue

                            # oh well -- it could be in the cache

                        except Exception as e:  # TODO what can be thrown here?
                            raise e

                    # is this analysis in the cache?
                    cached_result = await self.get_cached_analysis_result(observable, amt)
                    if cached_result:
                        get_logger().debug(
                            f"using cached result {cached_result} for {observable} type {amt} in {target_root}"
                        )

                        new_ar.original_root = cached_result.original_root
                        new_ar.modified_root = cached_result.modified_root
                        new_ar.cache_hit = True
                        await self.track_analysis_request(new_ar)
                        observable.track_analysis_request(new_ar)
                        await target_root.update_and_save()
                        await self.fire_event(EVENT_CACHE_HIT, [target_root, observable, new_ar])
                        await self.process_analysis_request(new_ar)
                        continue

                    # otherwise we need to request it
                    get_logger().info(
                        f"creating new analysis request for observable {observable} amt {amt} root {target_root}"
                    )
                    # (we also track the request inside the RootAnalysis object)
                    observable.track_analysis_request(new_ar)
                    # track_analysis_request(new_ar)
                    await target_root.update_and_save()
                    await self.fire_event(EVENT_PROCESSING_REQUEST_OBSERVABLE, new_ar)
                    await self.submit_analysis_request(new_ar)
                    continue

        # at this point this AnalysisRequest is no longer needed
        await self.delete_analysis_request(ar)

        # has all the analysis completed for this root?
        if target_root.all_analysis_completed():
            get_logger().debug(f"completed root analysis {ar.root}")
            await self.fire_event(EVENT_ANALYSIS_ROOT_COMPLETED, ar.root)

        # should this root expire now?
        if await ar.root.is_expired():
            get_logger().debug(f"deleting expired root analysis {ar.root}")
            await self.fire_event(EVENT_ANALYSIS_ROOT_EXPIRED, ar.root)
            await self.delete_root_analysis(ar.root)

    @coreapi
    async def get_cached_analysis_result(
        self, observable: Observable, amt: AnalysisModuleType
    ) -> Union[AnalysisRequest, None]:
        cache_key = generate_cache_key(observable, amt)
        if cache_key is None:
            return None

        return await self.i_get_cached_analysis_result(cache_key)

    async def i_get_cached_analysis_result(self, cache_key: str) -> Union[AnalysisRequest, None]:
        """Returns the cached AnalysisRequest for the analysis with the given cache key, or None if it does not exist."""
        raise NotImplementedError()

    @coreapi
    async def cache_analysis_result(self, request: AnalysisRequest) -> Union[str, None]:
        assert isinstance(request, AnalysisRequest)
        assert request.is_observable_analysis_result

        cache_key = generate_cache_key(request.observable, request.type)
        if cache_key is None:
            return None

        get_logger().debug(f"caching analysis request {request} with key {cache_key} ttl {request.type.cache_ttl}")
        result = await self.i_cache_analysis_result(cache_key, request, request.type.cache_ttl)
        await self.fire_event(EVENT_CACHE_NEW, [cache_key, request])
        return result

    async def i_cache_analysis_result(self, cache_key: str, request: AnalysisRequest, expiration: Optional[int]) -> str:
        """Caches the AnalysisRequest to the cache key and returns the cache id."""
        raise NotImplementedError()

    @coreapi
    async def delete_expired_cached_analysis_results(self):
        get_logger().debug(f"deleting expired cached analysis results")
        await self.i_delete_expired_cached_analysis_results()

    async def i_delete_expired_cached_analysis_results(self):
        """Deletes all cache results that have expired."""
        raise NotImplementedError()

    @coreapi
    async def delete_cached_analysis_results_by_module_type(self, amt: AnalysisModuleType):
        get_logger().debug(f"deleting cached analysis results for analysis module type {amt}")
        await self.i_delete_cached_analysis_results_by_module_type(amt)

    async def i_delete_cached_analysis_results_by_module_type(self, amt: AnalysisModuleType):
        """Deletes all cache results for the given type."""
        raise NotImplementedError()

    #
    # instrumentation
    #

    @coreapi
    async def get_cache_size(self, amt: Optional[AnalysisModuleType] = None):
        return await self.i_get_cache_size(amt)

    async def i_get_cache_size(self, amt: Optional[AnalysisModuleType] = None) -> int:
        """Returns the total number of cached results. If no type is specified
        then the total size of all cached results are returned.  Otherwise the
        total size of all cached results for the given type are returned."""
        raise NotImplementedError()

    #
    # configuration
    #

    async def get_config_value(
        self,
        key: str,
        default: Optional[Any] = None,
        env: Optional[str] = None,
    ) -> Any:
        """Returns the value of the configuration setting.  If the configuration setting is not found and env is not None
        then the OS environment variable in the env parameter is used. Only plain string values can be used with environment
        variables.  Otherwise, default is returned, None if default is not defined."""
        assert isinstance(key, str) and key
        assert env is None or (isinstance(env, str) and str)

        result = await self.get_config(key)
        if result is not None:
            return result.value

        if result is None and env and env in os.environ:
            return os.environ[env]

        return default

    @coreapi
    async def get_config(self, key: str) -> Union[ConfigurationSetting, None]:
        assert isinstance(key, str) and key
        return await self.i_get_config(key)

    async def i_get_config(self, key: str) -> ConfigurationSetting:
        """Returns a ace.data_model.ConfigurationSetting object for the setting, or None if the setting does not
        exist."""
        raise NotImplementedError()

    @coreapi
    async def set_config(self, key: str, value: Any, documentation: Optional[str] = None):
        """Sets the configuration setting. This function updates the setting if it already exists, or creates a new one if
        it did not."""
        assert isinstance(key, str) and key
        assert documentation is None or isinstance(documentation, str) and documentation

        if value is None and documentation is None:
            raise ValueError("cannot set configuration value to None")

        get_logger().debug(f"modified config key {key}")
        result = await self.i_set_config(key, value, documentation)
        await self.fire_event(EVENT_CONFIG_SET, [key, value, documentation])
        return result

    async def i_set_config(self, key: str, value: Any, documentation: Optional[str] = None):
        """Sets the configuration setting.

        Args:
            key: the configuration setting
            value: any value supported by the pydantic json encoder, values of None are ignored
            documentation: optional free-form documentation for the configuration setting, values of None are ignored

        """

        raise NotImplementedError()

    @coreapi
    async def delete_config(self, key: str) -> bool:
        """Deletes the configuration setting. Returns True if the setting was deleted."""
        assert isinstance(key, str) and key

        get_logger().debug(f"deleted config key {key}")
        result = await self.i_delete_config(key)
        if result:
            await self.fire_event(EVENT_CONFIG_DELETE, key)

        return result

    async def i_delete_config(self, key: str) -> bool:
        """Deletes the configuration setting. Returns True if the configuration setting was deleted, False otherwise."""
        raise NotImplementedError()

    #
    # events
    #

    @coreapi
    async def register_event_handler(self, event: str, handler: EventHandler):
        get_logger().debug(f"registering event handler for {event}: {handler}")
        return await self.i_register_event_handler(event, handler)

    async def i_register_event_handler(self, event: str, handler: EventHandler):
        """Adds an EventHandler for the given event.
        If this handler is already installed for this event then no action is taken."""

        raise NotImplementedError()

    @coreapi
    async def remove_event_handler(self, handler: EventHandler, events: Optional[list[str]] = []):
        get_logger().debug(f"removing event handler {handler}")
        return await self.i_remove_event_handler(handler, events)

    async def i_remove_event_handler(self, handler: EventHandler, events: Optional[list[str]] = []):
        """Removes an EventHandler. The handler is removed from the events specified, or all events if none are specified."""
        raise NotImplementedError()

    @coreapi
    async def get_event_handlers(self, event: str) -> list[EventHandler]:
        return await self.i_get_event_handlers(event)

    async def i_get_event_handlers(self, event: str) -> list[EventHandler]:
        """Returns the list of registered event handlers for the given event."""
        raise NotImplementedError()

    @coreapi
    async def fire_event(self, event: str, event_args: Optional[Any] = None):
        """Fires the event with the given JSON argument."""
        assert isinstance(event, str) and event

        get_logger().debug(f"fired event {event}")
        return await self.i_fire_event(Event(name=event, args=event_args))

    async def i_fire_event(self, event: Event):
        """Calls all registered event handlers for the given event.
        There is no requirement that handlers are called in any particular order."""
        raise NotImplementedError()

    #
    # storage
    #

    @coreapi
    async def store_content(self, content: Union[bytes, str, io.IOBase], meta: ContentMetadata) -> str:
        assert isinstance(content, bytes) or isinstance(content, str) or isinstance(content, io.IOBase)
        assert isinstance(meta, ContentMetadata)
        get_logger().debug(f"storing content {meta}")
        sha256 = await self.i_store_content(content, meta)
        await self.fire_event(EVENT_STORAGE_NEW, [sha256, meta])
        return sha256

    async def i_store_content(self, content: Union[bytes, str, io.IOBase], meta: ContentMetadata) -> str:
        """Stores the content with the given meta data and returns the key needed to lookup the content.

        Args:
            content: the content to store
            meta: metadata about the content

        Returns:
            the lookup key for the content (sha256 hash)
        """
        raise NotImplementedError()

    @coreapi
    async def load_file(self, sha256: str, path: str) -> Union[ContentMetadata, None]:
        return await self.i_load_file(sha256, path)

    async def i_load_file(self, sha256: str, path: str) -> Union[ContentMetadata, None]:
        """Saves the content of the given file into path and returns the
        metadata.  The purpose of this function is to transfer the content into
        the target file in the most efficient way possible."""
        raise NotImplementedError()

    @coreapi
    async def get_content_bytes(self, sha256: str) -> Union[bytes, None]:
        return await self.i_get_content_bytes(sha256)

    async def i_get_content_bytes(self, sha256: str) -> Union[bytes, None]:
        """Returns the requested stored content as a bytes object, or None if the content does not exist."""
        raise NotImplementedError()

    @coreapi
    async def iter_content(
        self, sha256: str, buffer_size: Optional[int] = io.DEFAULT_BUFFER_SIZE
    ) -> Union[AsyncGenerator[bytes, None], None]:
        async for _buffer in self.i_iter_content(sha256, buffer_size):
            yield _buffer

    async def i_iter_content(self, sha256: str, buffer_size: int) -> Union[AsyncGenerator[bytes, None], None]:
        raise NotImplementedError()

    @coreapi
    async def save_file(self, path: str, **kwargs) -> Union[str, None]:
        return await self.i_save_file(path, **kwargs)

    async def i_save_file(self, path: str, **kwargs) -> Union[str, None]:
        """Stores the contents of the given file and returns the sha256 hash.
        The purpose of this function is to transfer the content from the target
        file in the most efficient way possible."""
        raise NotImplementedError()

    @coreapi
    async def get_content_meta(self, sha256: str) -> Union[ContentMetadata, None]:
        return await self.i_get_content_meta(sha256)

    async def i_get_content_meta(self, sha256: str) -> Union[ContentMetadata, None]:
        """Returns the meta data of the stored content, or None if the content does not exist."""
        raise NotImplementedError()

    @coreapi
    async def iter_expired_content(self) -> Iterator[ContentMetadata]:
        """Returns an iterator for all the expired content."""
        return self.i_iter_expired_content()

    async def i_iter_expired_content(self) -> Iterator[ContentMetadata]:
        """Iterates over expired content metadata."""
        raise NotImplementedError()

    @coreapi
    async def delete_content(self, sha256: str) -> bool:
        get_logger().debug(f"deleting content {sha256}")
        result = await self.i_delete_content(sha256)
        if result:
            await self.fire_event(EVENT_STORAGE_DELETED, sha256)

        return result

    async def i_delete_content(self, sha256: str) -> bool:
        """Deletes the given content. Returns True if content was actually deleted."""
        raise NotImplementedError()

    @coreapi
    async def track_content_root(self, sha256: str, root: Union[RootAnalysis, str]):
        assert isinstance(sha256, str)
        assert isinstance(root, RootAnalysis) or isinstance(root, str)

        if isinstance(root, RootAnalysis):
            root = root.uuid

        get_logger().debug(f"tracking content {sha256} to root {root}")
        await self.i_track_content_root(sha256, root)

    async def i_track_content_root(self, sha256: str, uuid: str):
        """Associates stored content to a root analysis."""
        raise NotImplementedError()

    @coreapi
    async def has_valid_root_reference(self, meta: ContentMetadata) -> bool:
        """Returns True if the given meta has a valid (existing) RootAnalysis reference."""
        for root_uuid in meta.roots:
            if await get_root_analysis(root_uuid) is not None:
                return True

        return False

    @coreapi
    async def delete_expired_content(self) -> int:
        """Deletes all expired content and returns the number of items deleted."""
        get_logger().debug("deleting expired content")
        count = 0
        async for meta in await self.iter_expired_content():
            root_exists = False
            for root_uuid in meta.roots:
                if await self.analyis_tracking.get_root_analysis(root_uuid) is not None:
                    root_exists = True
                    break

            if root_exists:
                continue

            if await self.delete_content(meta.sha256):
                count += 1

        return count

    #
    # work queue
    #

    @coreapi
    async def delete_work_queue(self, amt: Union[AnalysisModuleType, str]) -> bool:
        assert isinstance(amt, AnalysisModuleType) or isinstance(amt, str)

        if isinstance(amt, AnalysisModuleType):
            amt = amt.name

        get_logger().debug(f"deleting work queue for {amt}")
        result = await self.i_delete_work_queue(amt)
        if result:
            await self.fire_event(EVENT_WORK_QUEUE_DELETED, amt)

        return result

    async def i_delete_work_queue(self, name: str) -> bool:
        """Deletes an existing work queue.
        A deleted work queue is removed from the system, and all work items in the queue are also deleted."""
        raise NotImplementedError()

    @coreapi
    async def add_work_queue(self, amt: Union[AnalysisModuleType, str]) -> bool:
        assert isinstance(amt, AnalysisModuleType) or isinstance(amt, str)
        if isinstance(amt, AnalysisModuleType):
            amt = amt.name

        get_logger().debug(f"adding work queue for {amt}")
        result = await self.i_add_work_queue(amt)
        if result:
            await self.fire_event(EVENT_WORK_QUEUE_NEW, amt)

        return result

    async def i_add_work_queue(self, name: str) -> bool:
        """Creates a new work queue for the given analysis module type.
        Returns True if a new queue was actually created, False otherwise.
        If the work queue already exists then this function returns False."""
        raise NotImplementedError()

    @coreapi
    async def put_work(self, amt: Union[AnalysisModuleType, str], analysis_request: AnalysisRequest):
        assert isinstance(amt, AnalysisModuleType) or isinstance(amt, str)
        assert isinstance(analysis_request, AnalysisRequest)

        if isinstance(amt, AnalysisModuleType):
            amt = amt.name

        get_logger().debug(f"adding request {analysis_request} to work queue for {amt}")
        result = await self.i_put_work(amt, analysis_request)
        await self.fire_event(EVENT_WORK_ADD, [amt, analysis_request])
        return result

    async def i_put_work(self, amt: str, analysis_request: AnalysisRequest):
        """Adds the AnalysisRequest to the end of the work queue for the given type."""
        raise NotImplementedError()

    @coreapi
    async def get_work(self, amt: Union[AnalysisModuleType, str], timeout: int) -> Union[AnalysisRequest, None]:
        assert isinstance(amt, AnalysisModuleType) or isinstance(amt, str)
        assert isinstance(timeout, int)

        if isinstance(amt, AnalysisModuleType):
            amt = amt.name

        result = await self.i_get_work(amt, timeout)
        if result:
            await self.fire_event(EVENT_WORK_REMOVE, [amt, result])

        return result

    async def i_get_work(self, amt: str, timeout: int) -> Union[AnalysisRequest, None]:
        """Gets the next AnalysisRequest from the work queue for the given type, or None if no content is available.

        Args:
            timeout: how long to wait in seconds
            Passing 0 returns immediately

        """
        raise NotImplementedError()

    @coreapi
    async def get_queue_size(self, amt: Union[AnalysisModuleType, str]) -> int:
        assert isinstance(amt, AnalysisModuleType) or isinstance(amt, str)

        if isinstance(amt, AnalysisModuleType):
            amt = amt.name

        return await self.i_get_queue_size(amt)

    async def i_get_queue_size(self, amt: str) -> int:
        """Returns the current size of the work queue for the given type."""
        raise NotImplementedError()

    @coreapi
    async def get_next_analysis_request(
        self,
        owner_uuid: str,
        amt: Union[AnalysisModuleType, str],
        timeout: Optional[int] = 0,
        version: Optional[str] = None,
        extended_version: Optional[list[str]] = [],
    ) -> Union[AnalysisRequest, None]:
        """Returns the next AnalysisRequest for the given AnalysisModuleType, or None if nothing is available.
        This function is called by the analysis modules to get the next work item.

        Args:
            owner_uuid: Represents the owner of the request.
            amt: The AnalysisModuleType that the request is for.
            timeout: How long to wait (in seconds) for a work request to come in.
                Defaults to 0 seconds which immediately returns a result.
            version: Optional module version. If you pass the name for the amt
                parameter then you must also pass the version and (optionally) the
                extended version.
            extended_version: Optional module extended version.


        Returns:
            An AnalysisRequest to be processed, or None if no work requests are available."""

        assert isinstance(owner_uuid, str) and owner_uuid
        assert isinstance(amt, AnalysisModuleType) or (isinstance(amt, str) and amt)
        assert isinstance(timeout, int)
        assert version is None or (isinstance(version, str) and version)
        assert isinstance(extended_version, list)

        # did we just pass the name and version?
        if isinstance(amt, str):
            if version is None:
                raise ValueError("missing required version parameter when passing amt as string")

            amt = AnalysisModuleType(name=amt, description="", version=version, extended_version=extended_version)

        # make sure that the requested analysis module hasn't been replaced by a newer version
        # if that's the case then the request fails and the requestor needs to update to the new version
        existing_amt = await self.get_analysis_module_type(amt.name)
        if existing_amt and not existing_amt.version_matches(amt):
            get_logger().info(f"requested amt {amt} version mismatch against {existing_amt}")
            raise AnalysisModuleTypeVersionError(amt, existing_amt)

        if existing_amt and not existing_amt.extended_version_matches(amt):
            get_logger().info(f"requested amt {amt} extended version mismatch against {existing_amt}")
            raise AnalysisModuleTypeExtendedVersionError(amt, existing_amt)

        # make sure expired analysis requests go back in the work queues
        await self.process_expired_analysis_requests(amt)

        # we don't need to do any locking here because of how the work queues work
        while True:
            next_ar = await self.get_work(amt, timeout)

            if next_ar:
                # get the most recent copy of the analysis request
                next_ar = await self.get_analysis_request_by_request_id(next_ar.id)
                # if it was deleted then we ignore it and move on to the next one
                # this can happen if the request is deleted while it's waiting in the queue
                if not next_ar:
                    get_logger().warning("unknown request {next_ar} aquired from work queue for {amt}")
                    continue

                # set the owner, status then update
                next_ar.owner = owner_uuid
                next_ar.status = TRACKING_STATUS_ANALYZING
                get_logger().debug(f"assigned analysis request {next_ar} to {owner_uuid}")
                await self.track_analysis_request(next_ar)
                await self.fire_event(EVENT_WORK_ASSIGNED, next_ar)

            return next_ar

    encryption_settings: EncryptionSettings = None

    #
    # authentication
    #

    @coreapi
    async def create_api_key(
        self, name: str, description: Optional[str] = None, is_admin: Optional[bool] = False
    ) -> str:
        """Creates a new api_key. Returns the newly created api_key."""
        if not self.encryption_settings:
            raise MissingEncryptionSettingsError()

        return await self.i_create_api_key(name, description, is_admin)

    async def i_create_api_key(self, name: str, description: Optional[str] = None) -> Union[str, None]:
        raise NotImplementedError()

    @coreapi
    async def delete_api_key(self, name: str) -> bool:
        """Deletes the given api key. Returns True if the key was deleted, False otherwise."""
        if not self.encryption_settings:
            raise MissingEncryptionSettingsError()

        return await self.i_delete_api_key(name)

    async def i_delete_api_key(self, name: str) -> bool:
        raise NotImplementedError()

    @coreapi
    async def verify_api_key(self, api_key: str, is_admin: Optional[bool] = False) -> bool:
        """Returns True if the given api key is valid, False otherwise. If
        is_admin is True then the api_key must also be an admin key to pass
        verification."""
        return await self.i_verify_api_key(api_key, is_admin)

    async def i_verify_api_key(self, api_key: str) -> bool:
        raise NotImplementedError()

    #
    # audit
    #

    async def audit(self, action: str, user: str, details: str):
        """Appends the given action and user (and optional details) to the audit log."""
        raise NotImplementedError()

    #
    # encryption
    #

    #
    # tokenization
    #

    def new_root(self, *args, **kwargs):
        """Returns a new RootAnalysis object for this system."""
        from ace.analysis import RootAnalysis

        return RootAnalysis(system=self, *args, **kwargs)

    # XXX reset is really just for unit testing
    async def reset(self):
        pass

    # should be called before start() is called
    async def initialize(self):
        pass

    # called to start the system
    def start(self):
        pass

    # called to stop the system
    def stop(self):
        pass
