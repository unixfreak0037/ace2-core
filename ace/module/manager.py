# vim: ts=4:sw=4:et:cc=120
#

import asyncio
import concurrent.futures
import logging
import multiprocessing
import os
import signal
import uuid

from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass
from typing import Optional

from ace.api import get_api
from ace.api.base import AceAPI, AnalysisRequest
from ace.error_reporting.reporter import format_error_report
from ace.module.base import AnalysisModule
from ace.analysis import RootAnalysis, Analysis
from ace.system.analysis_module import AnalysisModuleTypeVersionError, AnalysisModuleTypeExtendedVersionError

import psutil

# possible results of compute_scaling
SCALE_UP = 1
NO_SCALING = 0
SCALE_DOWN = -1

#
# concurrency routines
#

# concurrency mode for non-async analysis modules
# defaults to threaded
CONCURRENCY_MODE_THREADED = 1
CONCURRENCY_MODE_PROCESS = 2

#
# process-based concurrency uses empty processes to do the work
# all the arguments to the process are serialized (using pickle)
# we don't want to have to serialize the instance of the analysis module
# that would not work for module that load large data sets to do their work
# (such as yara analyzers)
# so instead, when the process starts, we use the initializer to load
# all the analysis modules
# these are passed in as a dict { name: [type, amt] }
# where name is AnalysisModuleType.name
# type is type(AnalysisModule)
# amt is AnalysisModuleType
# we use these arguments to instantiate copies of the analysis modules
# and these instances of the analysis modules are kept in the global sync_module_map
# then to execute them, we just pass the name and look up the name
# in the global sync_module_map to get the analysis module to use
# then all that needs to be serialized is the name of the module and the analysis request
#

sync_module_map = None


def _initialize_executor(module_map):
    global sync_module_map
    sync_module_map = {}
    # TODO probably need to initialize logging here
    for module_name, params in module_map.items():
        _type, amt = params
        # create a new instance of the analysis module
        sync_module_map[module_name] = _type(type=amt)
        logging.info(f"loaded {amt.name} in subprocess")
        # load any additional resources
        sync_module_map[module_name].load()


def _execute_sync_module(module_name: str, request_json: str) -> str:
    request = AnalysisRequest.from_json(request_json)
    module = sync_module_map[module_name]
    module.execute_analysis(request.modified_root, request.modified_observable)
    return request.to_json()


class AnalysisModuleManager:
    """Executes and manages ace.module.AnalysisModule objects."""

    def __init__(self, concurrency_mode=CONCURRENCY_MODE_THREADED, wait_time=0):
        # the analysis modules this manager is running
        self.analysis_modules = []
        self.analysis_module_map = {}  # key = AnalysisModule.type.name, value = AnalysisModule

        # current list of tasks
        self.module_tasks = []  # asyncio.Task
        self.module_task_count = {}  # key = AnalysisModule, value = int

        # executor for non-async modules
        self.concurrency_mode = concurrency_mode  # determines threading or multiprocessing
        self.executor = None

        # the amount of time (in seconds) to wait for analysis requests
        self.wait_time = wait_time  # defaults to not waiting

        #
        # state flags
        #

        # set to True to stop the manager gracefully (allowing existing tasks to complete)
        self.shutdown = False

        # set to True to stop immediately
        self.immediate_shutdown = False

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
        # by default we never scale up
        # implement custom algorithms in subclasses
        return SCALE_DOWN

    def add_module(self, module: AnalysisModule) -> AnalysisModule:
        """Adds the given AnalysisModule to this manager. Duplicate modules are ignored.
        Returns the added module, or None if the module already existed."""
        if type(module) not in [type(_) for _ in self.analysis_modules]:
            self.analysis_modules.append(module)
            self.analysis_module_map[module.type.name] = module
            self.module_task_count[module] = 0
            return module
        else:
            return None

    def _new_module_task(self, module: AnalysisModule, whoami: str):
        # adds a new analysis module task to the event loop
        task = asyncio.create_task(self.module_loop(module, whoami), name=f"module {module.type.name}:{whoami}")
        self.module_tasks.append(task)

    def initialize_module_tasks(self):
        """Creates the initial set of analysis module tasks, one for each loaded analysis module."""
        for module in self.analysis_modules:
            self.create_module_task(module)

    def create_module_task(self, module: AnalysisModule, whoami: Optional[str] = None):
        """Creates a new analysis module task if the limit of the module allows it."""
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
        """Continues execution of the module."""
        self._new_module_task(module, whoami)

    def stop_module_task(self, module: AnalysisModule, whoami: str):
        """Stops execution of the module."""
        self.module_task_count[module] -= 1

    def start_executor(self):
        module_map = {_.type.name: [type(_), _.type] for _ in self.analysis_modules}

        # executor for non-async modules
        if self.concurrency_mode == CONCURRENCY_MODE_THREADED:
            self.executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=multiprocessing.cpu_count(), initializer=_initialize_executor, initargs=(module_map,)
            )
        else:
            self.executor = concurrent.futures.ProcessPoolExecutor(
                initializer=_initialize_executor, initargs=(module_map,)
            )

    def kill_executor(self):
        if self.concurrency_mode != CONCURRENCY_MODE_PROCESS:
            return

        for process in psutil.Process(os.getpid()).children():
            logging.warning(f"sending KILL to {process}")
            process.send_signal(signal.SIGTERM)

    async def run_once(self) -> bool:
        """Run once through the analysis routine and exit."""
        self.shutdown = True
        return await self.run()

    async def run(self) -> bool:
        """Run the analysis routine. Does not return until all tasks have completed."""
        # download current registration and compare
        if not await self.verify_registration():
            return False

        # start the executor for the non-async analysis modules
        self.start_executor()

        # start initial analysis tasks
        self.initialize_module_tasks()

        # primary loop
        module_tasks = self.module_tasks[:]
        self.module_tasks = []
        while module_tasks:
            # done, pending = await asyncio.wait(module_tasks, timeout=0.1, return_when=asyncio.FIRST_COMPLETED)
            done, pending = await asyncio.wait(module_tasks, timeout=0.01)
            # if the system is shutting down then we go ahead and cancel any new and/or pending tasks
            if self.immediate_shutdown:
                for task in pending:
                    task.cancel()
                for task in self.module_tasks:
                    task.cancel()

            self.module_tasks.extend(pending)
            module_tasks = self.module_tasks[:]
            self.module_tasks = []
            for completed_task in done:
                try:
                    module = await completed_task
                except asyncio.CancelledError as e:
                    logging.warning(f"task {completed_task.get_name()} was cancelled before it completed")

        self.executor.shutdown(wait=False, cancel_futures=True)
        self.kill_executor()
        return True

    def stop(self):
        """Gracefully stops the manager. Allows existing jobs to complete."""
        self.shutdown = True

    def force_stop(self):
        """Stops the manager now, cancelling all running jobs."""
        self.shutdown = True
        self.immediate_shutdown = True

    async def module_loop(self, module: AnalysisModule, whoami: str):
        """Entrypoint for analysis module execution."""
        request = None

        try:
            request = await get_api().get_next_analysis_request(whoami, module.type, self.wait_time)
        except AnalysisModuleTypeExtendedVersionError as e:
            logging.info(f"module {module.type.name} has invalid extended version: {e}")

            # attempt to upgrade the module
            try:
                module.upgrade()
            except Exception as e:
                logging.error(f"unable to upgrade module {module.type.name}: {e}")
                self.shutdown = True

        except AnalysisModuleTypeVersionError as e:
            logging.info(f"module {module.type.name} has invalid version: {e}")
            self.shutdown = True

        scaling = self.compute_scaling(module)
        if not self.shutdown and scaling == SCALE_UP:
            self.create_module_task(module)

        if request:
            request = await self.execute_module(module, whoami, request)

        # we just continue executing if there is no scaling required
        # OR this is the last task for this module
        # (there should always be one running)
        if not self.shutdown and (scaling == NO_SCALING or self.module_task_count[module] == 1):
            self.continue_module_task(module, whoami)
        elif self.shutdown or scaling == SCALE_DOWN:
            self.stop_module_task(module, whoami)

        # it is ok to wait here
        # we continue analysis on a new task
        if request:
            await get_api().submit_analysis_request(request)

        return module

    async def execute_module(self, module: AnalysisModule, whoami: str, request: AnalysisRequest) -> AnalysisRequest:
        """Processes the request with the analysis module.
        Returns a copy of the original request with the results added"""

        assert isinstance(module, AnalysisModule)
        assert isinstance(whoami, str) and whoami
        assert isinstance(request, AnalysisRequest)

        request.initialize_result()
        if module.is_async():
            try:
                await module.execute_analysis(request.modified_root, request.modified_observable)
                return request
            except Exception as e:
                logging.error(
                    f"{module} failed analyzing {request.modified_observable.type} {request.modified_observable.value}: {e}"
                )
                return self.process_exception(module, request, e)
        else:
            try:
                request_json = request.to_json()
                request_result_json = await asyncio.get_event_loop().run_in_executor(
                    self.executor, _execute_sync_module, module.type.name, request_json
                )
                return AnalysisRequest.from_json(request_result_json)
            except BrokenProcessPool as e:
                # when this happens you have to create and start a new one
                logging.error(f"{module} crashed when analyzing {request}")
                self.process_exception(
                    module,
                    request,
                    e,
                    error_message=f"{module.type.name} process crashed when analyzing {request.modified_observable.type} {request.modified_observable.value}",
                )
                # we have to start a new executor
                self.start_executor()
                return request
            except Exception as e:
                logging.error(
                    f"{module} failed analyzing {request.modified_observable.type} {request.modified_observable.value}: {e}"
                )
                return self.process_exception(module, request, e)

    def process_exception(
        self, module: AnalysisModule, request: AnalysisRequest, e: Exception, error_message: Optional[str] = None
    ) -> AnalysisRequest:
        assert isinstance(module, AnalysisModule)
        assert isinstance(request, AnalysisRequest)
        assert isinstance(e, Exception)

        # use existing analysis if it already exists
        analysis = request.modified_observable.get_analysis(module.type)
        if analysis is None:
            analysis = request.modified_observable.add_analysis(Analysis(type=module.type))

        # set the error message and stack trace details
        if not error_message:
            analysis.error_message = f"{type(e).__name__}: {e}"
        else:
            analysis.error_message = error_message
        analysis.stack_trace = format_error_report(e)
        return request
