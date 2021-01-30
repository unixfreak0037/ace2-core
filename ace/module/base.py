# vim: ts=4:sw=4:et:cc=120
#

import inspect
import multiprocessing
import uuid

from dataclasses import dataclass, field
from typing import Optional

from ace.api import get_api
from ace.api.analysis import AnalysisModuleType


class AnalysisModule:
    """Base class for analysis modules.
    Override the execute_analysis function to implement analysis logic.
    Override the upgrade function to implement custom upgrade logic."""

    type: Optional[AnalysisModuleType] = None

    def __init__(self, type: Optional[AnalysisModuleType] = None, limit: Optional[int] = None):
        if type is None:
            self.type = AnalysisModuleType(f"anonymous-{uuid.uuid4()}", "")
        else:
            self.type = type

        if limit is None:
            if self.is_async():
                self.limit = 3  # XXX ???
            else:
                self.limit = multiprocessing.cpu_count()
        else:
            self.limit = limit

    # def register(self) -> AnalysisModuleType:
    # return get_api().register_analysis_module_type(self.type)

    def is_async(self) -> bool:
        return inspect.iscoroutinefunction(self.execute_analysis)

    def execute_analysis(self, root, observable) -> bool:
        raise NotImplementedError()

    def upgrade(self):
        pass

    def __hash__(self):
        return self.type.name.__hash__()
