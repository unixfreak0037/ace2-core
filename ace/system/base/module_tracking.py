# vim: ts=4:sw=4:et:cc=120
#
#
#

from typing import Union, Optional

from ace import coreapi
from ace.logging import get_logger
from ace.analysis import AnalysisModuleType
from ace.constants import *
from ace.exceptions import AnalysisModuleTypeDependencyError, CircularDependencyError


class AnalysisModuleTrackingBaseInterface:
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
