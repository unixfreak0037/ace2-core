# vim: ts=4:sw=4:et:cc=120
#

import inspect
import multiprocessing
import uuid

from dataclasses import dataclass, field
from typing import Optional, Union

from ace.api import get_api
from ace.analysis import RootAnalysis, AnalysisModuleType, Observable, Analysis

DEFAULT_ASYNC_LIMIT = 3  # XXX ???


class AnalysisModule:
    """Base class for analysis modules.
    Override the execute_analysis function to implement analysis logic.
    Override the upgrade function to implement custom upgrade logic."""

    type: AnalysisModuleType = None
    limit: int = None
    timeout: Union[float, int] = None

    def __init__(
        self, type: Optional[AnalysisModuleType] = None, limit: Optional[int] = None, timeout: Union[int, float] = None
    ):
        if type:
            self.type = type
        elif self.type is None:
            self.type = AnalysisModuleType(f"anonymous-{uuid.uuid4()}", "")

        if limit:
            self.limit = limit
        elif self.limit is None:
            if self.is_async():
                self.limit = DEFAULT_ASYNC_LIMIT
            else:
                self.limit = multiprocessing.cpu_count()

        if timeout:
            self.timeout = timeout

    # def register(self) -> AnalysisModuleType:
    # return get_api().register_analysis_module_type(self.type)

    def is_async(self) -> bool:
        return inspect.iscoroutinefunction(self.execute_analysis)

    def execute_analysis(self, root: RootAnalysis, observable: Observable, analysis: Analysis):
        raise NotImplementedError()

    def upgrade(self):
        pass

    # XXX I think we can get rid of this with a correct design
    def load(self):
        pass

    def __hash__(self):
        return self.type.name.__hash__()


class AsyncAnalysisModule(AnalysisModule):
    async def execute_analysis(self, root: RootAnalysis, observable: Observable, analysis: Analysis):
        raise NotImplementedError()

    async def upgrade(self):
        pass

    async def load(self):
        pass
