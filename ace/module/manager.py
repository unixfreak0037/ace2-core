# vim: ts=4:sw=4:et:cc=120
#

import asyncio
import concurrent.futures
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
        self.analysis_modules = []
        self.limits = {}  # key = AnalysisModule, value = asyncio.Semaphore
        self.cpu_limits = {}  # key = AnalysisModule, value = asyncio.Semaphore
        self.executions = []  # asyncio.Task
        self.executor = None

    def add_module(self, module: AnalysisModule) -> AnalysisModule:
        if module not in self.analysis_modules:
            self.analysis_modules.append(module)

        return module

    def compute_scaling(self, module: AnalysisModule) -> int:
        return SCALE_DOWN

    def load_analysis_modules(self):
        # TODO
        self.analysis_modules = [AnalysisModule()]

    async def verify_registration(self) -> bool:
        return True

    async def register(self) -> bool:
        for module in self.analysis_modules:
            result = await get_api().register_analysis_module_type(module.type)

        return True

    async def run(self) -> bool:
        # load analysis modules
        # register all analysis modules
        # create limits for all amts
        # start a LIMIT

        # self.load_analysis_modules()

        # download current registration and compare
        if not await self.verify_registration():
            return False

        if not await self.register():
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

            scale = self.compute_scaling(module)
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


# LIMIT
# GET
# SCALE
# ANALYZE
# RESULT
