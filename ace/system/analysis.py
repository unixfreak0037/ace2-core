# vim: sw=4:ts=4:et:cc=120

import ace.analysis

from ace.analysis import Observable

class AnalysisModuleType(ace.analysis.AnalysisModuleType):

    @staticmethod
    def from_dict(value: dict, _cls_map=None) -> "AnalysisModuleType":
        return ace.analysis.from_dict(value, _cls_map=get_cls_map())

    @staticmethod
    def from_json(value: str, _cls_map=None) -> "AnalysisModuleType":
        return ace.analysis.from_json(value, _cls_map=get_cls_map())

    def accepts(self, observable: Observable) -> bool:
        from ace.system.analysis_module import get_analysis_module_type

        assert isinstance(observable, Observable)

        # has this module been requested?
        if observable.is_requested(self):
            return True

        # if this module is manual and it wasn't requested then we don't execute it
        if self.manual:
            return False

        # has this analysis type been excluded from this observable?
        if self.name in observable.excluded_analysis:
            return False

        # TODO conditions are OR vertical AND horizontal?

        # OR
        if self.modes and observable.root.analysis_mode not in self.modes:
            return False

        # OR
        if self.observable_types:
            if observable.type not in self.observable_types:
                return False

        # AND
        for directive in self.directives:
            if not observable.has_directive(directive):
                return False

        # AND
        for tag in self.tags:
            if not observable.has_tag(tag):
                return False

        # AND (this is correct)
        for dep in self.dependencies:
            amt = get_analysis_module_type(dep)
            if amt is None:
                logging.debug(f"{observable} has unknown dependency {dep}")
                return False

            if not observable.analysis_completed(amt):
                return False

        # has this observable been limited to specific analysis modules?
        if observable.limited_analysis:
            for amt in observable.limited_analysis:
                if self.name == amt:
                    return True

            # if we didn't match anything in this list then we didn't match the
            # thing(s) it is limited to
            return False

        return True

class Analysis(ace.analysis.Analysis):

    @staticmethod
    def from_dict(value: dict, root: "RootAnalysis", analysis: Optional["Analysis"] = None, _cls_map=None) -> "Analysis":
        return ace.analysis.Analysis.from_dict(value, root, analysis, _cls_map=get_cls_map())

    @staticmethod
    def from_json(value: str, root: "RootAnalysis", analysis: Optional["Analysis"] = None, _cls_map=None) -> "Analysis":
        return ace.analysis.Analysis.from_json(value, root, analysis, _cls_map=get_cls_map())

    def save(self) -> bool:
        """Saves the current results of the Analysis."""
        from ace.system.analysis_tracking import track_analysis_details

        if self._details_modified:
            if track_analysis_details(self.root, self.uuid, self._details):
                self._details_modified = False
                return True
            else:
                return False
        else:
            return False

    def flush(self):
        """Calls save() and then clears the details property.  It must be load()ed again."""
        self.save()
        self._details = None

    @property
    async def details(self):
        return self._details
        # do we already have the details loaded or set?
        if self._details is not None:
            return self._details

        # load the external details and return those results
        await self._load_details()
        return self._details

    @details.setter
    def details(self, value):
        self._details = value
        self._details_modified = True

    def _load_details(self):
        """Returns the details referenced by this object as a dict or None if the operation failed."""
        # NOTE you should never call this directly
        # this is called whenever .details is requested and it hasn't been loaded yet

        if self._details_modified:
            logging.warning("called _load_details() after details where modified")

        if self._details is not None:
            logging.warning("called _load_details() after details was already set")

        try:
            from ace.system.analysis_tracking import get_analysis_details

            self._details = get_analysis_details(self.uuid)
            self._details_modified = False

            if self._details is None:
                logging.warning(f"missing analysis details for {self.uuid}")

            return self._details

        except Exception as e:
            logging.error("unable to load analysis details {self.uuid}: {e}")
            raise e

    def add_file(self, path: str, **kwargs) -> "Observable":
        """Utility function that adds a file observable to the root analysis by passing a path to the file."""
        from ace.system.storage import store_file

        return self.add_observable("file", store_file(path, roots=[self.uuid], **kwargs))

class RootAnalysis(ace.analysis.RootAnalysis):

    @staticmethod
    def from_dict(value: dict, _cls_map=None) -> "RootAnalysis":
        return ace.analysis.RootAnalysis.from_dict(value, _cls_map=get_cls_map())

    @staticmethod
    def from_json(value: str, _cls_map=None) -> "RootAnalysis":
        return ace.analysis.RootAnalysis.from_json(value, _cls_map=get_cls_map())

    def is_expired(self):
        """Returns True if this root has expired."""
        from ace.system.analysis_request import get_analysis_requests_by_root

        # is it set to expire
        if not self.expires:
            return False

        # does it have any detection points?
        if self.has_detection_points():
            return False

        # are there any outstanding analysis requests?
        if get_analysis_requests_by_root(self.uuid):
            return False

        return True

    def save(self):
        from ace.system.analysis_tracking import track_root_analysis

        track_root_analysis(self)

        for analysis in self.all_analysis:
            if analysis is not self:
                analysis.save()

        # save our own details
        return Analysis.save(self)

    def __del__(self):
        # make sure that any remaining storage directories are wiped out
        if self.discard():
            logging.warning(f"discard() was not called on {self}")

    def discard(self) -> bool:
        """Discards a local RootAnalysis object. This has the effect of
        deleting the storage directory for this analysis, which deletes any
        files that were downloaded.

        Returns True if something was deleted, False otherwise."""
        if self.storage_dir and os.path.exists(self.storage_dir):
            shutil.rmtree(self.storage_dir)
            logging.debug(f"deleted {self.storage_dir}")
            self.storage_dir = None
            return True

        return False

    def submit(self):
        """Submits this RootAnalysis for analysis."""
        from ace.system.analysis_request import submit_analysis_request

        return submit_analysis_request(self.create_analysis_request())

def get_cls_map() -> dict:
    return {
        "Analysis": Analysis,
        "AnalysisModuleType": AnalysisModuleType,
        "Observable": ace.analysis.Observable,
        "RootAnalysis": RootAnalysis
    }
