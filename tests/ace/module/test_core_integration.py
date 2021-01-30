# vim: ts=4:sw=4:et:cc=120
#

#
# XXX this in particular is going to be super confusing
# we're using ace.system.analysis and ace.api.analysis in the same code here
#

import ace.system.analysis
import ace.api.analysis

from ace.system.analysis import RootAnalysis, Observable
from ace.system.analysis_tracking import get_root_analysis
from ace.system.analysis_module import register_analysis_module_type
from ace.api.analysis import AnalysisModuleType, Analysis
from ace.module.base import AnalysisModule
from ace.module.manager import AnalysisModuleManager

import pytest


@pytest.mark.unit
@pytest.mark.asyncio
async def test_basic_analysis_async(event_loop):

    # basic analysis module
    class TestAsyncAnalysisModule(AnalysisModule):
        # define the type for this analysis module
        type = ace.api.analysis.AnalysisModuleType("test", "")

        # define it as an async module
        async def execute_analysis(
            self, root: ace.api.analysis.RootAnalysis, observable: ace.api.analysis.Observable
        ) -> bool:
            analysis = observable.add_analysis(ace.api.analysis.Analysis(type=self.type, details={"test": "test"}))
            analysis.add_observable("test", "hello")
            return True

    # create an instance of it
    module = TestAsyncAnalysisModule()

    # register the type to the core
    register_analysis_module_type(module.type)

    # submit a root for analysis so we create a new job
    root = ace.system.analysis.RootAnalysis()
    observable = root.add_observable("test", "test")
    root.submit()

    # create a new manager to run our analysis modules
    manager = AnalysisModuleManager()
    manager.add_module(module)
    await manager.run_once()

    # check the results in the core
    root = get_root_analysis(root)
    observable = root.get_observable(observable)
    analysis = observable.get_analysis(module.type)
    assert analysis
    assert analysis.details == {"test": "test"}
    assert analysis.observables[0] == ace.system.analysis.Observable("test", "hello")
