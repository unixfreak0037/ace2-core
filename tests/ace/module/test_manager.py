# vim: ts=4:sw=4:et:cc=120
#

from ace.api.local import LocalAceAPI
from ace.module.base import AnalysisModule
from ace.module.manager import AnalysisModuleManager

import pytest


@pytest.mark.unit
@pytest.mark.asyncio
async def test_manager_start(event_loop):
    await AnalysisModuleManager().run()


@pytest.mark.unit
def test_add_module():
    class CustomAnalysisModule(AnalysisModule):
        pass

    manager = AnalysisModuleManager()
    module = CustomAnalysisModule()
    assert manager.add_module(module) is module
    assert module in manager.analysis_modules
    # insert same instance twice fails
    assert manager.add_module(module) is None
    module = CustomAnalysisModule()
    # insert another instance of a class already added fails
    assert manager.add_module(module) is None

    class CustomAnalysisModule2(AnalysisModule):
        pass

    module_2 = CustomAnalysisModule2()
    assert manager.add_module(module_2) is module_2
    assert len(manager.analysis_modules) == 2
