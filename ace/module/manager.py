# vim: ts=4:sw=4:et:cc=120
#

import asyncio
import concurrent.futures
import uuid

from ace.api.base import AceAPI
from ace.module.base import AnalysisModule

SCALE_UP = 1
NO_SCALING = 0
SCALE_DOWN = -1

# XXX
WAIT_TIME = 0


class AnalysisModuleManager:
    def __init__(self, core_api: AceAPI = None):
        assert core_api

        self.core_api = core_api
        self.analysis_modules = []
        self.limits = {}  # key = AnalysisModule, value = asyncio.Semaphore
        self.cpu_limits = {}  # key = AnalysisModule, value = asyncio.Semaphore
        self.executions = []  # asyncio.Task
        self.executor = None

    def compute_scaling(self, module: AnalysisModule) -> int:
        return NO_SCALING

    def load_analysis_modules(self):
        # TODO
        self.analysis_modules = [AnalysisModule()]

    async def verify_registration(self) -> bool:
        return True

    async def register(self) -> bool:
        return True

    async def run(self) -> bool:
        # load analysis modules
        # register all analysis modules
        # create limits for all amts
        # start a LIMIT

        self.load_analysis_modules()
        # download current registration and compare
        if not await self.verify_registration():
            return False

        if not await self.register():
            return False

        # start initial analysis tasks
        for module in self.analysis_modules:
            self.executions.append(asyncio.create_task(self.execute_module(module, str(uuid.uuid4()))))

        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)  # XXX

        # primary loop
        executions = self.executions[:]
        self.executions = []
        while self.executions:
            done, pending = await asyncio.wait(self.executions)
            self.executions.extend(pending)

    async def execute_module(self, module: AnalysisModule, whoami: str):
        async with module.limiter:
            request = await self.core_api.get_next_analysis_request(actor_id, module.type, WAIT_TIME)

            scale = self.compute_scaling(module)
            if scale == SCALE_DOWN:
                # TODO am I allowed to scale down?
                return
            elif scale == SCALE_UP:
                # TODO am I allowed to scale up?
                self.executions.append(asyncio.create_task(self.execute_module(module, str(uuid.uuid4()))))

            if module.is_async():
                try:
                    result = await self.execute_analysis(request.root, request.observable)
                except Exception as e:
                    pass  # XXX
            else:
                try:
                    result = await asyncio.get_event_loop().run_in_executor(
                        self.executor, module.execute_analysis, request.root, request.observable
                    )
                except Exception as e:
                    pass  # XXX

        # drop out of the semaphore
        # do this again (use a new task)
        self.executions.append(asyncio.create_task(self.execute_module(module, whoami)))

        # use the existing task to post the results
        # TODO prepare the result...
        await self.core_api.submit_analysis_request(result)


# LIMIT
# GET
# SCALE
# ANALYZE
# RESULT
