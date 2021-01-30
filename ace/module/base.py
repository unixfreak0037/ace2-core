# vim: ts=4:sw=4:et:cc=120
#

import inspect
import multiprocessing
import uuid

from dataclasses import dataclass, field
from typing import Optional

from ace.api import get_api
from ace.api.analysis import AnalysisModuleType

# XXX
def get_default_async_limit():
    return 1


def get_default_sync_limit():
    """Return the default limit for non-async workers. Defaults to local cpu count."""
    return multiprocessing.cpu_count()


class AnalysisModule:

    type: Optional[AnalysisModuleType] = None

    def __init__(self, type: Optional[AnalysisModuleType] = None, limit: Optional[int] = None):
        if type is None:
            self.type = AnalysisModuleType(f"anonymous-{uuid.uuid4()}", "")
        else:
            self.type = type

        if limit is None:
            if self.is_async():
                self.limit = get_default_async_limit()
            else:
                self.limit = get_default_sync_limit()
        else:
            self.limit = limit

    def register(self) -> AnalysisModuleType:
        return get_api().register_analysis_module_type(self.type)

    def is_async(self) -> bool:
        return inspect.iscoroutinefunction(self.execute_analysis)

    def execute_analysis(self, root, observable) -> bool:
        raise NotImplementedError()

    def upgrade(self):
        pass

    def __hash__(self):
        return self.type.name.__hash__()
