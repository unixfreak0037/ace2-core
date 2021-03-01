# vim: ts=4:sw=4:et:cc=120
#

from ace.analysis import AnalysisModuleType, RootAnalysis
from ace.api import get_api
from ace.system.work_queue import AnalysisModuleTypeVersionError, AnalysisModuleTypeExtendedVersionError

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_get_next_analysis_request_invalid_version():
    amt = AnalysisModuleType(name="test", description="test", version="1.0.0", extended_version=["intel:v1"])

    await get_api().register_analysis_module_type(amt)
    with pytest.raises(AnalysisModuleTypeVersionError):
        response = await get_api().get_next_analysis_request("test", "test", 0, "1.0.1")

    with pytest.raises(AnalysisModuleTypeExtendedVersionError):
        response = await get_api().get_next_analysis_request("test", "test", 0, "1.0.0", extended_version=["intel:v0"])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_get_next_analysis_request():
    amt = AnalysisModuleType(name="test", description="test")

    request = await get_api().register_analysis_module_type(amt)
    assert await get_api().get_next_analysis_request("test", "test", 0, "1.0.0") is None

    root = RootAnalysis()
    observable = root.add_observable("test", "test")
    root.submit()

    request = await get_api().get_next_analysis_request("test", "test", 0, "1.0.0")
    assert request is not None
    assert request.root == root
    assert request.observable == observable
    assert request.type == amt
