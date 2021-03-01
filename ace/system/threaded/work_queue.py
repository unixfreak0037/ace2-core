# vim: ts=4:sw=4:et:cc=120

import queue
from typing import Union

from ace.system.analysis_request import AnalysisRequest
from ace.system.analysis_module import AnalysisModuleType
from ace.system.exceptions import UnknownAnalysisModuleTypeError
from ace.system.work_queue import WorkQueueManagerInterface


class ThreadedWorkQueueManagerInterface(WorkQueueManagerInterface):

    work_queues = {}  # key = amt.name, value = queue.Queue

    def delete_work_queue(self, analysis_module_name: str) -> bool:
        try:
            del self.work_queues[analysis_module_name]
            return True
        except KeyError:
            return False

    def add_work_queue(self, analysis_module_name: str) -> bool:
        if analysis_module_name not in self.work_queues:
            self.work_queues[analysis_module_name] = queue.Queue()
            return True

        return False

    def get_work(self, amt: str, timeout: int) -> Union[AnalysisRequest, None]:
        assert isinstance(amt, str)
        assert isinstance(timeout, int)

        try:
            return self.work_queues[amt].get(block=True, timeout=timeout)
        except KeyError:
            raise UnknownAnalysisModuleTypeError()
        except queue.Empty:
            return None

    def put_work(self, amt: str, analysis_request: AnalysisRequest):
        assert isinstance(amt, str)
        assert isinstance(analysis_request, AnalysisRequest)

        try:
            self.work_queues[amt].put(analysis_request)
        except KeyError:
            raise UnknownAnalysisModuleTypeError()

    def get_queue_size(self, amt: str) -> int:
        assert isinstance(amt, str)

        try:
            return self.work_queues[amt].qsize()
        except KeyError:
            raise UnknownAnalysisModuleTypeError()

    def reset(self):
        self.work_queues = {}
