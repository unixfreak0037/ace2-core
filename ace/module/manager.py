# vim: ts=4:sw=4:et:cc=120
#

import asyncio
import concurrent.futures
import logging
import uuid

from ace.api import get_api
from ace.api.base import AceAPI
from ace.module.base import AnalysisModule
from ace.analysis import RootAnalysis

SCALE_UP = 1
NO_SCALING = 0
SCALE_DOWN = -1

# XXX
WAIT_TIME = 0


class AnalysisModuleManager:
    def __init__(self):
        # the analysis modules this manager is running
        self.analysis_modules = []
        self.analysis_module_map = {}
        # current list of tasks
        self.executions = []  # asyncio.Task
        # executor for non-async modules
        self.executor = None
        # algorithm used for scaling
        self.scaling_algorithm = ScalingAlgorithm()

    def add_module(self, module: AnalysisModule) -> AnalysisModule:
        """Adds the given AnalysisModule to this manager. Duplicate modules are ignored."""
        if type(module) not in [type(_) for _ in self.analysis_modules]:
            self.analysis_modules.append(module)
            self.analysis_module_map[module.type.name] = module
            return module
        else:
            return None

    async def verify_registration(self) -> bool:
        """Ensure analysis modules are registered and up to date."""
        tasks = []
        for module in self.analysis_modules:
            async def check_type(module):
                result = await get_api().get_analysis_module_type(module.type.name)
                return module, result

            task = asyncio.get_event_loop().create_task(check_type(module))
            tasks.append(task)

        verification_ok = True
        for task in asyncio.as_completed(tasks):
            module, existing_type = await task
            if not existing_type:
                logging.critical(f"analysis module type {module.type.name} is not registered")
                verification_ok = False
                continue

            # is the version we have for this module different than the version already registered?
            if not self.analysis_module_map[existing_type.name].type.version_matches(existing_type):
                logging.critical(f"analysis module type {module.type.name} has a different version")
                verification_ok = False
                continue

            # is the extended version different?
            if not self.analysis_module_map[existing_type.name].type.extended_version_matches(existing_type):
                # try to upgrade the module
                self.analysis_module_map[existing_type.name].upgrade()
                # is it still different?
                if not self.analysis_module_map[existing_type.name].type.extended_version_matches(existing_type):
                    logging.critical(f"analysis module type {module.type.name} has a different extended version after upgrade")
                    verification_ok = False
                    continue

        return verification_ok

    async def run(self) -> bool:
        # load analysis modules
        # register all analysis modules
        # create limits for all amts
        # start a LIMIT

        # download current registration and compare
        if not await self.verify_registration():
            return False

        # executor for non-async modules
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)  # XXX use ProcessPool

        # start initial analysis tasks
        for module in self.analysis_modules:
            self.executions.append(asyncio.create_task(self.execute_module(module, str(uuid.uuid4()))))

        # primary loop
        executions = self.executions[:]
        self.executions = []
        while executions:
            done, pending = await asyncio.wait(executions)
            self.executions.extend(pending)
            executions = self.executions[:]
            for completed_task in done:
                result = await completed_task

    async def execute_module(self, module: AnalysisModule, whoami: str):
        async with module.limiter:
            request = await get_api().get_next_analysis_request(whoami, module.type, WAIT_TIME)

            scale = self.scaling_algorithm.compute_scaling(self, module)
            if scale == SCALE_UP:
                # TODO am I allowed to scale up?
                self.executions.append(asyncio.create_task(self.execute_module(module, str(uuid.uuid4()))))

            analysis_result = None

            if request:
                request.initialize_result()
                if module.is_async():
                    try:
                        analysis_result = await module.execute_analysis(
                            request.modified_root, request.modified_observable
                        )
                    except Exception as e:
                        # do something
                        raise e  # XXX
                else:
                    try:
                        analysis_result = await asyncio.get_event_loop().run_in_executor(
                            self.executor, module.execute_analysis, request.modified_root, request.modified_observable
                        )
                    except Exception as e:
                        # do something
                        raise e  # XXX

        # drop out of the semaphore
        # do this again (use a new task)
        if scale != SCALE_DOWN:
            self.executions.append(asyncio.create_task(self.execute_module(module, whoami)))

        # use the existing task to post the results
        # TODO prepare the result...
        if request:
            await get_api().submit_analysis_request(request)


class ScalingAlgorithm:
    """Represents the algorithm used to scale workers up or down for a given module."""

    def compute_scaling(self, manager: AnalysisModuleManager, module: AnalysisModule) -> int:
        """Compute the scaling for the given module. Returns
        SCALE_UP: to increase the number of workers by 1.
        SCALE_DOWN: to decrease the number of workers by 1.
        NO_SCALING: to keep current levels."""
        return SCALE_DOWN

