# vim: ts=4:sw=4:et:cc=120
#

from ace.api import get_api
from ace.api.analysis import AnalysisModuleType
from ace.api.local import LocalAceAPI
from ace.module.base import AnalysisModule
from ace.module.manager import AnalysisModuleManager

import pytest

class CustomAnalysisModule(AnalysisModule):
    pass

class CustomAnalysisModule2(AnalysisModule):
    pass

@pytest.mark.unit
@pytest.mark.asyncio
async def test_manager_start(event_loop):
    await AnalysisModuleManager().run()


@pytest.mark.unit
def test_add_module():
    manager = AnalysisModuleManager()
    module = CustomAnalysisModule()
    assert manager.add_module(module) is module
    assert module in manager.analysis_modules
    # insert same instance twice fails
    assert manager.add_module(module) is None
    module = CustomAnalysisModule()
    # insert another instance of a class already added fails
    assert manager.add_module(module) is None
    module_2 = CustomAnalysisModule2()
    assert manager.add_module(module_2) is module_2
    assert len(manager.analysis_modules) == 2

@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_registration():
    # registration OK
    amt = AnalysisModuleType("test", "", additional_cache_keys=["yara:6f5902ac237024bdd0c176cb93063dc4"])

    assert await get_api().register_analysis_module_type(amt)

    manager = AnalysisModuleManager()
    manager.add_module(CustomAnalysisModule(amt))
    assert await manager.verify_registration()
    # missing registration
    amt = AnalysisModuleType("missing", "")
    manager = AnalysisModuleManager()
    manager.add_module(CustomAnalysisModule(amt))
    assert not await manager.verify_registration()
    # version mismatch
    amt = AnalysisModuleType("test", "", version="1.0.1")
    manager = AnalysisModuleManager()
    manager.add_module(CustomAnalysisModule(amt))
    assert not await manager.verify_registration()
    # extended version mismatch
    amt = AnalysisModuleType("test", "", additional_cache_keys=["yara:71bec09d78fe6abdb94244a4cc89c740"])
    manager = AnalysisModuleManager()
    manager.add_module(CustomAnalysisModule(amt))
    assert not await manager.verify_registration()
    # extended version mismatch but upgrade ok
    class UpgradableAnalysisModule(AnalysisModule):
        def upgrade(self):
            self.type.additional_cache_keys = ["yara:6f5902ac237024bdd0c176cb93063dc4"]

    # starts out with the wrong set of yara rules but upgrade() fixes that
    amt = AnalysisModuleType("test", "", additional_cache_keys=["yara:71bec09d78fe6abdb94244a4cc89c740"])
    manager = AnalysisModuleManager()
    manager.add_module(UpgradableAnalysisModule(amt))
    assert await manager.verify_registration()
