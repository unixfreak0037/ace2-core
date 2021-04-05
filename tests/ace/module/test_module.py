# vim: ts=4:sw=4:et:cc=120
#

import multiprocessing

from ace.analysis import AnalysisModuleType
from ace.module.base import AnalysisModule, MultiProcessAnalysisModule, DEFAULT_ASYNC_LIMIT

import pytest


@pytest.mark.unit
def test_analysis_module_constructor():
    # default sync module
    module = MultiProcessAnalysisModule()
    assert isinstance(module.type, AnalysisModuleType)
    assert module.limit == multiprocessing.cpu_count()
    assert module.timeout is None

    # default async module
    module = AnalysisModule()
    assert isinstance(module.type, AnalysisModuleType)
    assert module.limit == DEFAULT_ASYNC_LIMIT
    assert module.timeout is None

    # parameters specified
    amt = AnalysisModuleType("test", "")
    module = AnalysisModule(amt, 1, 2)
    assert module.type == amt
    assert module.limit == 1
    assert module.timeout == 2
