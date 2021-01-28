# vim: sw=4:ts=4:et:cc=120

import ace.analysis
from ace.api import get_api

class Analysis(ace.analysis.Analysis):

    @staticmethod
    def from_dict(value: dict, root: "RootAnalysis", analysis: Optional["Analysis"] = None, _cls_map=None) -> "Analysis":
        return ace.analysis.Analysis.from_dict(value, root, analysis, _cls_map=get_cls_map())

    @staticmethod
    def from_json(value: str, root: "RootAnalysis", analysis: Optional["Analysis"] = None, _cls_map=None) -> "Analysis":
        return ace.analysis.Analysis.from_json(value, root, analysis, _cls_map=get_cls_map())

    @property
    async def details(self):
        return self._details
        # do we already have the details loaded or set?
        if self._details is not None:
            return self._details

        # load the external details and return those results
        await self._load_details()
        return self._details

    async def _load_details(self):
        """Returns the details referenced by this object as a dict or None if the operation failed."""
        # NOTE you should never call this directly
        # this is called whenever .details is requested and it hasn't been loaded yet

        if self._details_modified:
            logging.warning("called _load_details() after details where modified")

        if self._details is not None:
            logging.warning("called _load_details() after details was already set")

        try:
            self._details = await get_api().get_analysis_details(self.uuid)
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
        "RootAnalysis": RootAnalysis
    }
