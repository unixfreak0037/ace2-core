# vim: ts=4:sw=4:et:cc=120
#

import asyncio
import concurrent.futures
import logging
import uuid

from dataclasses import dataclass
from typing import Optional

from ace.api import get_api
from ace.api.base import AceAPI, AnalysisRequest
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
        self.analysis_module_map = {}  # key = AnalysisModule.type.name, value = AnalysisModule
        # current list of tasks
        self.module_tasks = []  # asyncio.Task
        self.module_task_count = {}  # key = AnalysisModule, value = int
        # executor for non-async modules
        self.executor = None

        #
        # state flags
        #

        # set to True to stop the manager
        self.shutdown = False

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
                    logging.critical(
                        f"analysis module type {module.type.name} has a different extended version after upgrade"
                    )
                    verification_ok = False
                    continue

        return verification_ok

    def compute_scaling(self, module: AnalysisModule) -> int:
        """Compute the scaling for the given module. Returns
        SCALE_UP: to increase the number of workers by 1.
        SCALE_DOWN: to decrease the number of workers by 1.
        NO_SCALING: to keep current levels."""
        return SCALE_DOWN

    def add_module(self, module: AnalysisModule) -> AnalysisModule:
        """Adds the given AnalysisModule to this manager. Duplicate modules are ignored."""
        if type(module) not in [type(_) for _ in self.analysis_modules]:
            self.analysis_modules.append(module)
            self.analysis_module_map[module.type.name] = module
            self.module_task_count[module] = 0
            return module
        else:
            return None

    def _new_module_task(self, module: AnalysisModule, whoami: str):
        task = asyncio.create_task(self.module_loop(module, whoami))
        self.module_tasks.append(task)

    def initialize_module_tasks(self):
        for module in self.analysis_modules:
            self.create_module_task(module)

    def create_module_task(self, module: AnalysisModule, whoami: Optional[str] = None):
        if whoami is None:
            whoami = str(uuid.uuid4())

        if self.module_task_count[module] < module.limit:
            self._new_module_task(module, whoami)
            if module not in self.module_task_count:
                self.module_task_count[module] = 0

            self.module_task_count[module] += 1
        else:
            pass  # TODO notify we are trying to scale above the limit

    def continue_module_task(self, module: AnalysisModule, whoami: str):
        self._new_module_task(module, whoami)

    def stop_module_task(self, module: AnalysisModule, whoami: str):
        self.module_task_count[module] -= 1

    async def run_once(self) -> bool:
        self.shutdown = True
        return await self.run()

    async def run(self) -> bool:
        # download current registration and compare
        if not await self.verify_registration():
            return False

        # executor for non-async modules
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)  # XXX use ProcessPool

        # start initial analysis tasks
        self.initialize_module_tasks()

        # TODO fix cpu spin here
        # primary loop
        module_tasks = self.module_tasks[:]
        self.module_tasks = []
        while module_tasks:
            done, pending = await asyncio.wait(module_tasks)
            self.module_tasks.extend(pending)
            module_tasks = self.module_tasks[:]
            self.module_tasks = []
            for completed_task in done:
                module = await completed_task

    async def module_loop(self, module: AnalysisModule, whoami: str):
        request = await get_api().get_next_analysis_request(whoami, module.type, WAIT_TIME)
        scaling = self.compute_scaling(module)
        if not self.shutdown and scaling == SCALE_UP:
            self.create_module_task(module)

        if request:
            result = await self.execute_module(module, whoami, request)
        else:
            result = None

        # we just continue executing if there is no scaling required
        # OR this is the last task for this module
        # (there should always be one running)
        if not self.shutdown and (scaling == NO_SCALING or self.module_task_count[module] == 1):
            self.continue_module_task(module, whoami)
        elif self.shutdown or scaling == SCALE_DOWN:
            self.stop_module_task(module, whoami)

        if result:
            # it is ok to wait here
            # we continue analysis on a new task
            await get_api().submit_analysis_request(request)

        return module

    async def execute_module(self, module: AnalysisModule, whoami: str, request: AnalysisRequest) -> bool:
        assert isinstance(module, AnalysisModule)
        assert isinstance(whoami, str) and whoami
        assert isinstance(request, AnalysisRequest)

        request.initialize_result()
        if module.is_async():
            try:
                return await module.execute_analysis(request.modified_root, request.modified_observable)
            except Exception as e:
                # do something
                # raise e  # XXX
                return False
        else:
            try:
                return await asyncio.get_event_loop().run_in_executor(
                    self.executor, module.execute_analysis, request.modified_root, request.modified_observable
                )
            except Exception as e:
                # do something
                # raise e  # XXX
                return False
