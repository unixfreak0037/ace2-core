# vim: ts=4:sw=4:et:cc=120

import queue
from typing import Union

from ace.system.analysis_request import AnalysisRequest
from ace.system.analysis_module import AnalysisModuleType
from ace.system.work_queue import WorkQueueManagerInterface, WorkQueue


class DatabaseWorkQueue(WorkQueue):
    def put(self, analysis_request: AnalysisRequest):
        raise NotImplementedError()

    def get(self, timeout: int) -> Union[AnalysisRequest, None]:
        raise NotImplementedError()

    def size(self) -> int:
        raise NotImplementedError()


class DatabaseWorkQueueManagerInterface(WorkQueueManagerInterface):

    def invalidate_work_queue(self, analysis_module_name: str) -> bool:
        raise NotImplementedError()

    def add_work_queue(self, analysis_module_name: str) -> WorkQueue:
        raise NotImplementedError()

    def get_work_queue(self, amt: AnalysisModuleType) -> Union[WorkQueue, None]:
        raise NotImplementedError()
