# vim: ts=4:sw=4:et:cc=120

from typing import Union

from ace.analysis import AnalysisModuleType
from ace.system import ACESystem
from ace.system.analysis_request import AnalysisRequest


class RemoteAnalysisRequestTrackingInterface(ACESystem):
    async def process_analysis_request(self, ar: AnalysisRequest):
        return await self.get_api().process_analysis_request(ar)
