# vim: ts=4:sw=4:et:cc=120
#

import asyncio
import inspect

# XXX
def get_default_async_limit():
    return 1

def get_default_sync_limit():
    return 1

class AnalysisModule:

    limiter: asyncio.Semaphore
    type = None # AnalysisModuleType

    def __init__(self, *args, limit:int=None, **kwargs):
        super().__init__(*args, **kwargs)
        if limit is None:
            if self.is_async():
                limit = get_default_async_limit()
            else:
                limit = get_default_sync_limit()

        self.limiter = asyncio.Semaphore(limit)

    def is_async(self) -> bool:
        return inspect.iscoroutinefunction(self.execute_analysis)

    def execute_analysis(self, root, observable):
        pass
