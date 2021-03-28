# vim: ts=4:sw=4:et:cc=120

from typing import Union

from ace.analysis import AnalysisModuleType
from ace.system.base import AnalysisRequestTrackingBaseInterface
from ace.system.base.analysis_request import AnalysisRequest


class RemoteAnalysisRequestTrackingInterface(AnalysisRequestTrackingBaseInterface):
    async def process_analysis_request(self, ar: AnalysisRequest):
        return await self.get_api().process_analysis_request(ar)
