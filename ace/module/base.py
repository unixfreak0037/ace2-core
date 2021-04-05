# vim: ts=4:sw=4:et:cc=120
#

import multiprocessing
import uuid

from dataclasses import dataclass, field
from typing import Optional, Union

from ace.analysis import RootAnalysis, AnalysisModuleType, Observable, Analysis

DEFAULT_ASYNC_LIMIT = 3  # XXX ???


class AnalysisModule:
    """Base class for analysis modules.
    Override the execute_analysis function to implement analysis logic.
    Override the upgrade function to implement custom upgrade logic."""

    type: AnalysisModuleType = None
    limit: int = None
    timeout: Union[float, int] = None
    is_multi_process: bool = False

    def __init__(
        self,
        type: Optional[AnalysisModuleType] = None,
        limit: Optional[int] = None,
        timeout: Union[int, float] = None,
        is_multi_process: Optional[bool] = None,
    ):
        assert type is None or isinstance(type, AnalysisModuleType)
        assert limit is None or isinstance(limit, int)
        assert timeout is None or (isinstance(timeout, int) or isinstance(timeout, float))
        assert is_multi_process is None or isinstance(is_multi_process, bool)

        if type:
            self.type = type
        elif self.type is None:
            self.type = AnalysisModuleType(f"anonymous-{uuid.uuid4()}", "")

        # if this is True then execute_analysis is executed on a separate process so the async loop is not tied up
        # this is important for analysis modules that do a lot of CPU intensive tasks *IN PYTHON*
        # if you're I/O bound (network, file or external process) then you don't need this
        if is_multi_process is not None:
            self.is_multi_process = is_multi_process

        if limit is not None:
            self.limit = limit
        elif self.limit is None:
            if self.is_multi_process:
                self.limit = multiprocessing.cpu_count()
            else:
                self.limit = DEFAULT_ASYNC_LIMIT

        if timeout is not None:
            self.timeout = timeout

        # TODO implement a custom default timeout here

    async def execute_analysis(self, root: RootAnalysis, observable: Observable, analysis: Analysis):
        raise NotImplementedError()

    async def upgrade(self):
        pass

    # XXX I think we can get rid of this with a correct design
    async def load(self):
        pass

    def __hash__(self):
        return self.type.name.__hash__()


class MultiProcessAnalysisModule(AnalysisModule):
    """An analysis module that executes on a separate process."""

    is_multi_process = True
