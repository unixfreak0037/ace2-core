# vim: ts=4:sw=4:et:cc=120
#
#
#

from typing import Union

from ace import coreapi
from ace.logging import get_logger
from ace.constants import *
from ace.system.analysis_request import AnalysisRequest
from ace.analysis import Observable, AnalysisModuleType, RootAnalysis
from ace.exceptions import UnknownAnalysisModuleTypeError, ExpiredAnalysisRequestError


class AnalysisRequestTrackingBaseInterface:

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
