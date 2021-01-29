# vim: sw=4:ts=4:et:cc=120

from typing import Optional

import ace.analysis
from ace.analysis import AnalysisModuleType, Observable
from ace.api import get_api


class Analysis(ace.analysis.Analysis):
    @staticmethod
    def from_dict(
        value: dict, root: "RootAnalysis", analysis: Optional["Analysis"] = None, _cls_map=None
    ) -> "Analysis":
        return ace.analysis.Analysis.from_dict(value, root, analysis, _cls_map=get_cls_map())

    @staticmethod
    def from_json(value: str, root: "RootAnalysis", analysis: Optional["Analysis"] = None, _cls_map=None) -> "Analysis":
        return ace.analysis.Analysis.from_json(value, root, analysis, _cls_map=get_cls_map())

    @property
    def details(self):
        # details must be loaded
        if not self._details_loaded and not self._details_modified:
            raise ValueError("details not loaded or modified")

        return self._details

    @details.setter
    def details(self, value):
        self._details = value
        self._details_modified = True

    async def _load_details(self):
        """Returns the details referenced by this object as a dict or None if the operation failed."""

        if self._details_modified:
            logging.warning("called _load_details() after details where modified")

        if self._details is not None:
            logging.warning("called _load_details() after details was already set")

        try:
            self._details = await get_api().get_analysis_details(self.uuid)
            self._details_loaded = True
            self._details_modified = False

            if self._details is None:
                logging.warning(f"missing analysis details for {self.uuid}")

            return self._details

        except Exception as e:
            logging.error("unable to load analysis details {self.uuid}: {e}")
            raise e

    # XXX
    def add_file(self, path: str, **kwargs) -> "Observable":
        """Utility function that adds a file observable to the root analysis by passing a path to the file."""
        raise NotImplementedError()


class RootAnalysis(ace.analysis.RootAnalysis):
    @staticmethod
    def from_dict(value: dict, _cls_map=None) -> "RootAnalysis":
        return ace.analysis.RootAnalysis.from_dict(value, _cls_map=get_cls_map())

    @staticmethod
    def from_json(value: str, _cls_map=None) -> "RootAnalysis":
        return ace.analysis.RootAnalysis.from_json(value, _cls_map=get_cls_map())

    def discard(self) -> bool:
        raise NotImplementedError()

    async def submit(self):
        """Submits this RootAnalysis for analysis."""
        return await get_api().submit_analysis_request(self.create_analysis_request())


def get_cls_map() -> dict:
    return {
        "Analysis": Analysis,
        "AnalysisModuleType": ace.analysis.AnalysisModuleType,
        "Observable": ace.analysis.Observable,
        "RootAnalysis": RootAnalysis,
    }
