# vim: ts=4:sw=4:et:cc=120

import copy
import uuid
from typing import Union, Optional, Any

import ace.system

from ace.analysis import RootAnalysis, Observable, AnalysisModuleType, recurse_tree
from ace.data_model import AnalysisRequestModel, RootAnalysisModel
from ace.constants import (
    TRACKING_STATUS_NEW,
    TRACKING_STATUS_QUEUED,
    SYSTEM_LOCK_EXPIRED_ANALYSIS_REQUESTS,
    EVENT_AR_NEW,
    EVENT_AR_DELETED,
    EVENT_AR_EXPIRED,
    EVENT_ANALYSIS_ROOT_COMPLETED,
    EVENT_ANALYSIS_ROOT_EXPIRED,
    EVENT_CACHE_HIT,
    EVENT_PROCESSING_REQUEST_OBSERVABLE,
    EVENT_PROCESSING_REQUEST_RESULT,
    EVENT_PROCESSING_REQUEST_ROOT,
)
from ace.exceptions import (
    AnalysisRequestLockedError,
    ExpiredAnalysisRequestError,
    UnknownAnalysisRequestError,
    UnknownObservableError,
    UnknownRootAnalysisError,
    UnknownAnalysisModuleTypeError,
)


class AnalysisRequest:
    """Represents a request to analyze a single observable or a new analysis."""

    def __init__(
        self,
        system: "ace.system.ACESystem",
        root: Union[str, RootAnalysis],
        observable: Optional[Observable] = None,
        type: Optional[AnalysisModuleType] = None,
    ):

        from ace.system import ACESystem
        from ace.system.caching import generate_cache_key

        assert isinstance(system, ACESystem)
        assert isinstance(root, RootAnalysis) or isinstance(root, str)
        assert isinstance(observable, Observable) or observable is None
        assert isinstance(type, AnalysisModuleType) or type is None

        self.system = system

        # load existing analysis if root is passed in as a string uuid
        if isinstance(root, str):
            self.root = self.system.get_root_analysis(root)
        else:
            self.root = root

        #
        # static data
        #

        # generic unique ID of the request
        self.id = str(uuid.uuid4())
        # the Observable to be analyzed
        self.observable = observable
        # the type of analysis module to execute on this observable
        self.type = type
        # the key used to cache the analysis result
        # if this is a root analysis request or if the amt does not support caching then this is None
        self.cache_key = generate_cache_key(self.observable, self.type)
        # the RootAnalysis object this request belongs to or is entirely about
        # this can also be the UUID of the RootAnalysis
        # dict of analysis dependencies requested
        # key = analysis_module, value = Analysis
        self.dependency_analysis = {}
        # set to True if this observable analysis result is the result of a cache hit
        self.cache_hit = False

        #
        # dynamic data
        #

        # the current status of this analysis request
        self.status = TRACKING_STATUS_NEW
        # the UUID of the analysis module that is currently processing this request
        self.owner = None

        # the result of the analysis
        self.original_root = None
        self.modified_root = None

    def __eq__(self, other):
        if not isinstance(other, AnalysisRequest):
            return False

        return self.id == other.id

    def __str__(self):
        ar_type = "unknown"
        if self.is_observable_analysis_result:
            ar_type = "result"
        elif self.is_root_analysis_request:
            ar_type = "root"
        elif self.is_observable_analysis_request:
            ar_type = "request"

        return f"AnalysisRequest({ar_type},id={self.id},root={self.root},observable={self.observable},type={self.type})"

    def to_model(self, *args, **kwargs) -> AnalysisRequestModel:
        return AnalysisRequestModel(
            id=self.id,
            root=self.root if isinstance(self.root, str) else self.root.to_model(*args, **kwargs),
            observable=self.observable.to_model(*args, **kwargs) if self.observable else None,
            type=self.type.to_model(*args, **kwargs) if self.type else None,
            status=self.status,
            owner=self.owner,
            original_root=self.original_root.to_model(*args, **kwargs) if self.original_root else None,
            modified_root=self.modified_root.to_model(*args, **kwargs) if self.modified_root else None,
        )

    def to_dict(self, *args, **kwargs) -> dict:
        return self.to_model(*args, **kwargs).dict()

    def to_json(self, *args, **kwargs) -> str:
        return self.to_model(*args, **kwargs).json()

    @staticmethod
    def from_dict(value: dict, system: "ace.system.ACESystem") -> "AnalysisRequest":
        assert isinstance(value, dict)

        data = AnalysisRequestModel(**value)

        root = None
        if isinstance(data.root, RootAnalysisModel):
            root = RootAnalysis.from_dict(data.root.dict(), system=system)

        observable = None
        if data.observable:
            observable = Observable.from_dict(data.observable.dict(), root)
            observable = root.get_observable(observable)

        type = None
        if data.type:
            type = AnalysisModuleType.from_dict(data.type.dict())

        ar = AnalysisRequest(system, root, observable, type)
        ar.id = data.id
        # ar.dependency_analysis = json_data["dependency_analysis"]
        ar.status = data.status
        ar.owner = data.owner

        if data.original_root:
            ar.original_root = RootAnalysis.from_dict(data.original_root.dict(), system)

        if data.modified_root:
            ar.modified_root = RootAnalysis.from_dict(data.modified_root.dict(), system)

        return ar

    @staticmethod
    def from_json(value: str, system: Optional["ace.system.ACESystem"] = None) -> "AnalysisRequest":
        assert isinstance(value, str)
        return AnalysisRequest.from_dict(AnalysisRequestModel.parse_raw(value).dict(), system)

    #
    # utility functions
    #

    @property
    def is_cachable(self):
        """Returns True if the result of the analysis should be cached."""
        return self.cache_key is not None

    @property
    def is_observable_analysis_request(self) -> bool:
        """Was this a request to analyze an Observable?"""
        return self.observable is not None

    @property
    def is_observable_analysis_result(self) -> bool:
        """Does this include the result of the analysis?"""
        return self.result is not None

    @property
    def is_root_analysis_request(self) -> bool:
        """Was this a request to analyze a RootAnalysis?"""
        return self.observable is None

    @property
    def observables(self) -> list[Observable]:
        """Returns the list of all observables to analyze."""
        if self.is_observable_analysis_request:
            if self.is_observable_analysis_result:
                # process both the new observables and the one we already processed
                # doing so resolves dependencies
                observables = self.modified_observable.get_analysis(self.type).observables[:]
                observables.append(self.modified_observable)
                return observables
            else:
                # otherwise we just want to look at the observable
                return [self.observable]
        else:
            # otherwise we analyze all the observables in the entire RootAnalysis
            return self.root.all_observables

    @property
    def result(self):
        """Returns the RootAnalysis object that contains the results for this analysis."""
        return self.modified_root

    @property
    def modified_observable(self):
        """Returns a reference to the observable instance to use to store analysis results."""
        if self.modified_root is None:
            return None

        return self.modified_root.get_observable(self.observable)

    def initialize_result(self):
        """Initializes the results for this request."""
        self.original_root = self.root.copy()
        self.modified_root = self.root.copy()
        # self.original_root = copy.deepcopy(self.root)
        # self.modified_root = copy.deepcopy(self.root)
        return self.result

    async def submit(self):
        """Submits this analysis request for processing."""
        await self.system.submit_analysis_request(self)

    async def lock(self) -> bool:
        return await self.system.lock_analysis_request(self)

    async def unlock(self) -> bool:
        return await self.system.unlock_analysis_request(self)
