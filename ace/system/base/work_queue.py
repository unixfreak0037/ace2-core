# vim: ts=4:sw=4:et:cc=120
#
#
#

from typing import Union, Optional

from ace import coreapi
from ace.analysis import AnalysisModuleType
from ace.constants import *
from ace.system.analysis_request import AnalysisRequest
from ace.crypto import EncryptionSettings
from ace.logging import get_logger
from ace.exceptions import AnalysisModuleTypeVersionError, AnalysisModuleTypeExtendedVersionError


class WorkQueueBaseInterface:
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
