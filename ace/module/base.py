# vim: ts=4:sw=4:et:cc=120
#

import asyncio
import inspect

from dataclasses import dataclass, field
from typing import Optional

from ace.api import get_api
from ace.api.analysis import AnalysisModuleType

# XXX
def get_default_async_limit():
    return 1


def get_default_sync_limit():
    return 1


class AnalysisModule:

    type: AnalysisModuleType = field(default_factory=lambda: AnalysisModuleType("anonymous", ""))
    limiter: Optional[asyncio.Semaphore] = None

    def __init__(self, type: Optional[AnalysisModuleType] = None, limit: Optional[int] = None):
        if limit is None:
            if self.is_async():
                limit = get_default_async_limit()
            else:
                limit = get_default_sync_limit()

        self.limiter = asyncio.Semaphore(limit)

    def register(self) -> AnalysisModuleType:
        return get_api().register_analysis_module_type(self.type)

    def is_async(self) -> bool:
        return inspect.iscoroutinefunction(self.execute_analysis)

    def execute_analysis(self, root, observable) -> bool:
        raise NotImplementedError()
