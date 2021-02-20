# vim: ts=4:sw=4:et:cc=120
#

from ace.analysis import AnalysisModuleType
from ace.system.exceptions import AnalysisModuleTypeDependencyError
from ace.api import get_api

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_register_analysis_module():
    amt = AnalysisModuleType(name="test", description="test")

    assert await get_api().get_analysis_module_type(amt.name) is None
    assert await get_api().register_analysis_module_type(amt) == amt
    assert await get_api().get_analysis_module_type(amt.name) == amt

    amt = AnalysisModuleType(name="test", description="test", dependencies=["other"])

    with pytest.raises(AnalysisModuleTypeDependencyError):
        await get_api().register_analysis_module_type(amt)
