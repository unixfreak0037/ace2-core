# vim: ts=4:sw=4:et:cc=120
#

from ace.analysis import AnalysisModuleType
from ace.module.base import AnalysisModule
from ace.module.manager import AnalysisModuleManager, SCALE_UP, SCALE_DOWN, NO_SCALING

import pytest


@pytest.mark.asyncio
@pytest.mark.unit
async def test_add_module(manager):
    class CustomAnalysisModule(AnalysisModule):
        pass

    class CustomAnalysisModule2(AnalysisModule):
        pass

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


@pytest.mark.asyncio
@pytest.mark.unit
async def test_verify_registration(manager):
    # registration OK
    amt = AnalysisModuleType("test", "", extended_version={"yara": "6f5902ac237024bdd0c176cb93063dc4"})

    assert await manager.system.register_analysis_module_type(amt)

    custom_manager = AnalysisModuleManager(manager.system)
    custom_manager.add_module(AnalysisModule(amt))
    assert await custom_manager.verify_registration()
    # missing registration
    amt = AnalysisModuleType("missing", "")
    custom_manager = AnalysisModuleManager(manager.system)
    custom_manager.add_module(AnalysisModule(amt))
    assert not await custom_manager.verify_registration()
    assert not await custom_manager.run()
    # version mismatch
    amt = AnalysisModuleType("test", "", version="1.0.1")
    custom_manager = AnalysisModuleManager(manager.system)
    custom_manager.add_module(AnalysisModule(amt))
    assert not await custom_manager.verify_registration()
    assert not await custom_manager.run()
    # extended version mismatch
    amt = AnalysisModuleType("test", "", extended_version={"yara": "71bec09d78fe6abdb94244a4cc89c740"})
    custom_manager = AnalysisModuleManager(manager.system)
    custom_manager.add_module(AnalysisModule(amt))
    assert not await custom_manager.verify_registration()
    # extended version mismatch but upgrade ok
    class UpgradableAnalysisModule(AnalysisModule):
        async def upgrade(self):
            self.type.extended_version = {"yara": "6f5902ac237024bdd0c176cb93063dc4"}

    # starts out with the wrong set of yara rules but upgrade() fixes that
    amt = AnalysisModuleType("test", "", extended_version={"yara": "71bec09d78fe6abdb94244a4cc89c740"})
    custom_manager = AnalysisModuleManager(manager.system)
    custom_manager.add_module(UpgradableAnalysisModule(amt))
    assert await custom_manager.verify_registration()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_scaling_task_creation(manager):
    class CustomManager(AnalysisModuleManager):
        direction = SCALE_DOWN

        def compute_scaling(self, module):
            return self.direction

        def _new_module_task(self, module, whoami):
            self.module_tasks.append(object())

        def total_task_count(self):
            return sum(iter(self.module_task_count.values()))

    amt = AnalysisModuleType("test", "")
    custom_manager = CustomManager(manager.system)
    result = await custom_manager.system.register_analysis_module_type(amt)
    module = AnalysisModule(amt, limit=2)
    custom_manager.add_module(module)

    # no tasks to start
    assert custom_manager.total_task_count() == 0

    # starts with one task
    custom_manager.initialize_module_tasks()
    assert custom_manager.total_task_count() == 1

    # scale up to 2 tasks
    custom_manager.direction = SCALE_UP
    result = await custom_manager.module_loop(module, "test")
    assert custom_manager.total_task_count() == 2

    # should not scale past limit
    result = await custom_manager.module_loop(module, "test")
    assert custom_manager.total_task_count() == 2

    # scale down to one task
    custom_manager.direction = SCALE_DOWN
    result = await custom_manager.module_loop(module, "test")
    assert custom_manager.total_task_count() == 1

    # scale down does not drop below one task
    result = await custom_manager.module_loop(module, "test")
    assert custom_manager.total_task_count() == 1

    # after shutdown it drops to zero tasks
    custom_manager.shutdown = True
    await custom_manager.module_loop(module, "test")
    assert custom_manager.total_task_count() == 0
