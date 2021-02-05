# vim: sw=4:ts=4:et:cc=120


import copy
import datetime
import hashlib
import json
import logging
import os
import os.path
import pprint
import re
import shutil
import sys
import tempfile
import uuid

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Union, Optional, Any

import ace

from ace.system.exceptions import UnknownObservableError
from ace.system.locking import Lockable
from ace.time import parse_datetime_string, utc_now
from ace.data_model import (
    AnalysisModel,
    AnalysisModuleTypeModel,
    DetectableObjectModel,
    DetectionPointModel,
    ObservableModel,
    RootAnalysisModel,
    TaggableObjectModel,
)

#
# MERGING
#
# Merging exists primarily for purpose of applying cached observable analysis
# results. Analysis results stores changes made during analysis as a delta,
# which can be applied to another root.
#
# There are two merge functions that operate in two different ways. The
# target.apply_merge(source) function applies everything to the target that is
# in the source. The target.apply_diff_merge(before, after) function applies
# the delta between the before and after objects to the target.
#
# The diff_merge function is not recursive.
#


class MergableObject(ABC):
    """An object is mergable if a newer version of it can be merged into an older existing version."""

    @abstractmethod
    def apply_merge(self, target: "MergableObject") -> Union["MergableObject", None]:
        pass

    @abstractmethod
    def apply_diff_merge(self, before: "MergableObject", after: "MergableObject") -> Union["MergableObject", None]:
        pass


class DetectionPoint:
    """Represents an observation that would result in a detection."""

    def __init__(self, description=None, details=None):
        self.description = description
        self.details = details

    def to_model(self, *args, **kwargs) -> DetectionPointModel:
        return DetectionPointModel(description=self.description, details=self.details)

    def to_dict(self, *args, **kwargs) -> dict:
        return self.to_model(*args, **kwargs).dict()

    def to_json(self, *args, **kwargs) -> str:
        return self.to_model(*args, **kwargs).json()

    @staticmethod
    def from_dict(value: dict, detection_point: Optional["DetectionPoint"] = None, _cls_map=None) -> "DetectionPoint":
        assert isinstance(value, dict)
        assert detection_point is None or isinstance(detection_point, DetectionPoint)
        data = DetectionPointModel(**value)
        result = detection_point or DetectionPoint()
        result.description = data.description
        result.details = data.details
        return result

    @staticmethod
    def from_json(value: str, detection_point: Optional["DetectionPoint"] = None) -> "DetectionPoint":
        assert isinstance(value, str)
        assert detection_point is None or isinstance(detection_point, DetectionPoint)
        data = DetectionPointModel.parse_raw(value)
        return DetectionPoint.from_dict(data.dict(), detection_point)

    def __str__(self):
        return "DetectionPoint({})".format(self.description)

    def __eq__(self, other):
        if not isinstance(other, DetectionPoint):
            return False

        return self.description == other.description and self.details == other.details


class DetectableObject(MergableObject):
    """Mixin for objects that can have detection points."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._detections = []

    def to_model(self, *args, **kwargs) -> DetectableObjectModel:
        return DetectableObjectModel(detections=[DetectionPointModel(**_.to_dict()) for _ in self.detections])

    def to_dict(self, *args, **kwargs) -> dict:
        return self.to_model(*args, **kwargs).dict()

    def to_json(self, *args, **kwargs) -> str:
        return self.to_model(*args, **kwargs).json()

    @staticmethod
    def from_dict(value: dict, detectable_object: Optional["DetectableObject"] = None) -> "DetectableObject":
        assert isinstance(value, dict)
        assert detectable_object is None or isinstance(detectable_object, DetectableObject)
        data = DetectableObjectModel(**value)
        result = detectable_object or DetectableObject()
        result.detectables = [DetectionPoint.from_dict(_.dict()) for _ in data.detections]
        return result

    @staticmethod
    def from_json(value: str, detectable_object: Optional["DetectableObject"] = None) -> "DetectableObject":
        assert isinstance(value, str)
        assert detectable_object is None or isinstance(detectable_object, DetectableObject)
        return DetectableObject.from_dict(DetectableObjectModel.parse_raw(value).dict(), detectable_object)

    @property
    def detections(self):
        return self._detections

    @detections.setter
    def detections(self, value):
        assert isinstance(value, list)
        assert all([isinstance(x, DetectionPoint) for x in value])
        self._detections = value

    def has_detection_points(self):
        """Returns True if this object has at least one detection point, False otherwise."""
        return len(self._detections) != 0

    def add_detection_point(
        self, description_or_detection: Union[DetectionPoint, str], details: Optional[str] = None
    ) -> "DetectableObject":
        """Adds the given detection point to this object."""
        assert isinstance(description_or_detection, str) or isinstance(description_or_detection, DetectionPoint)

        if isinstance(description_or_detection, str):
            detection = DetectionPoint(description_or_detection, details)
        else:
            detection = description_or_detection

        if detection in self._detections:
            return self

        self._detections.append(detection)
        logging.debug(f"added detection point {detection} to {self}")
        return self

    def clear_detection_points(self):
        self._detections = {}

    def apply_merge(self, target: "DetectableObject") -> "DetectableObject":
        assert isinstance(target, DetectableObject)
        for detection in target.detections:
            self.add_detection_point(detection)

        return self

    def apply_diff_merge(self, before: "DetectableObject", after: "DetectableObject") -> "DetectableObject":
        assert isinstance(before, DetectableObject)
        assert isinstance(after, DetectableObject)
        for detection in after.detections:
            if detection not in before.detections:
                self.add_detection_point(detection)

        return self


class TaggableObject(MergableObject):
    """A mixin class that adds a tags property that is a list of tags assigned to this object."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # list of strings
        self._tags = []

    def to_model(self, *args, **kwargs) -> TaggableObjectModel:
        return TaggableObjectModel(tags=self.tags)

    def to_dict(self, *args, **kwargs) -> dict:
        return self.to_model(*args, **kwargs).dict()

    def to_json(self, *args, **kwargs) -> str:
        return self.to_model(*args, **kwargs).json()

    @staticmethod
    def from_dict(value: dict, taggable_object: Optional["TaggableObject"] = None) -> "TaggableObject":
        assert isinstance(value, dict)
        data = TaggableObjectModel(**value)
        result = taggable_object or TaggableObject()
        result.tags = data.tags
        return result

    @staticmethod
    def from_json(value: str, taggable_object: Optional["TaggableObject"] = None) -> "TaggableObject":
        assert isinstance(value, str)
        assert taggable_object is None or isinstance(taggable_object, TaggableObject)
        return TaggableObject.from_dict(TaggableObjectModel.parse_raw(value).dict(), taggable_object)

    @property
    def tags(self):
        return self._tags

    @tags.setter
    def tags(self, value):
        assert isinstance(value, list)
        assert all([isinstance(i, str) for i in value])
        self._tags = value

    def add_tag(self, tag: str) -> "TaggableObject":
        assert isinstance(tag, str)
        if tag in self.tags:
            return self

        self.tags.append(tag)
        logging.debug(f"added {tag} to {self}")
        return self

    def clear_tags(self):
        self._tags = []

    def has_tag(self, tag_value):
        """Returns True if this object has this tag."""
        return tag_value in self.tags

    def apply_merge(self, target: "TaggableObject") -> "TaggableObject":
        assert isinstance(target, TaggableObject)

        for tag in target.tags:
            self.add_tag(tag)

        return self

    def apply_diff_merge(self, before: "TaggableObject", after: "TaggableObject") -> "TaggableObject":
        assert isinstance(before, TaggableObject)
        assert isinstance(after, TaggableObject)

        for tag in after.tags:
            if tag not in before.tags:
                self.add_tag(tag)

        return self

    def __eq__(self, other) -> bool:
        if not isinstance(other, TaggableObject):
            return False

        return sorted(self.tags) == sorted(other.tags)


# forward declaraction
class Observable:
    pass


@dataclass
class AnalysisModuleType:
    """Represents a registration of an analysis module type."""

    # the name of the analysis module type
    name: str
    # brief English description of what the module does
    description: str
    # list of supported observable types (empty list supports all observable)
    observable_types: list[str] = field(default_factory=list)
    # list of required directives (empty list means no requirement)
    directives: list[str] = field(default_factory=list)
    # list of other analysis module type names to wait for (empty list means no deps)
    dependencies: list[str] = field(default_factory=list)
    # list of required tags (empty list means no requirement)
    tags: list[str] = field(default_factory=list)
    # list of valid analysis modes
    modes: list[str] = field(default_factory=list)
    # see TODO (insert link to conditions documentation)
    conditions: list[str] = field(default_factory=list)
    # the current version of the analysis module type
    version: str = "1.0.0"
    # how long this analysis module has before it times out (in seconds)
    # by default it takes the global default specified in the configuration file
    # you can set a very high timeout but nothing can never timeout
    timeout: int = 30
    # how long analysis results stay in the cache (in seconds)
    # a value of None means it is not cached
    cache_ttl: Optional[int] = None
    # what additional values should be included to determine the cache key?
    additional_cache_keys: list[str] = field(default_factory=list)
    # what kind of analysis module does this classify as?
    # examples: [ 'sandbox' ], [ 'splunk' ], etc...
    types: list[str] = field(default_factory=list)
    # if set to True then this analysis module only executes manually
    manual: bool = False

    def __post_init__(self):
        self.compiled_conditions = {}  # key = condition, value = compiled (something)

    def __str__(self):
        return f"{self.name}v{self.version}"

    #
    # json serialization
    #

    def to_model(self, *args, **kwargs) -> AnalysisModuleTypeModel:
        return AnalysisModuleTypeModel(**asdict(self))

    def to_dict(self, *args, **kwargs) -> dict:
        return self.to_model(*args, **kwargs).dict()

    def to_json(self, *args, **kwargs) -> str:
        return self.to_model(*args, **kwargs).json()

    @staticmethod
    def from_dict(value: dict, _cls_map=None) -> "AnalysisModuleType":
        if _cls_map is None:
            _cls_map = default_cls_map()

        data = AnalysisModuleTypeModel(**value)
        return _cls_map["AnalysisModuleType"](**data.dict())

    @staticmethod
    def from_json(value: str, _cls_map=None) -> "AnalysisModuleType":
        assert isinstance(value, str)
        if _cls_map is None:
            _cls_map = default_cls_map()

        return _cls_map["AnalysisModuleType"].from_dict(
            AnalysisModuleTypeModel.parse_raw(value).dict(), _cls_map=_cls_map
        )

    # ========================================================================

    def version_matches(self, amt) -> bool:
        """Returns True if the given amt is the same version as this amt."""
        return self.name == amt.name and self.version == amt.version
        # XXX should probably check the other fields as well

    def extended_version_matches(self, amt) -> bool:
        """Returns True if the given amt is the same version as this amt."""
        return (
            self.name == amt.name
            and self.version == amt.version
            and sorted(self.additional_cache_keys) == sorted(amt.additional_cache_keys)
        )

    @property
    def required_manual_directive(self) -> Union[str, None]:
        """Returns the directive that is required on the observable if manual is set to True."""
        if not self.manual:
            return None

        return f"manual:{self.name}"

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

        # AND
        for condition in self.conditions:
            if not self.condition_satisfied(condition, observable):
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

    def condition_satisfied(self, condition: str, observable: "Observable") -> bool:
        """Returns True if the given conditino is satisfied by the observable, False otherwise.
        TODO link to condition documentation."""

        # condition format is type:value
        _type, _value = condition.split(":", 1)

        # regular expression condition
        if _type == "re":
            # compile regex if we haven't already
            if condition not in self.compiled_conditions:
                try:
                    self.compiled_conditions[condition] = re.compile(_value)
                except Exception as e:
                    self.compiled_conditions[condition] = False
                    logging.error(f"regex condition {_value} from type {self.name} compliation failure: {e}")

            # if we failed to compile then the condition fails
            if not self.compiled_conditions[condition]:
                return False

            # to buffer to scan with the regex is the pretty-printed dict of the root
            pp = pprint.PrettyPrinter(indent=4, sort_dicts=True)
            target_buffer = pp.pformat(observable.root.to_dict())
            return self.compiled_conditions[condition].search(target_buffer, re.S)

        # python condition
        elif _type == "py3":
            # compile python code if we haven't already
            if condition not in self.compiled_conditions:
                try:
                    self.compiled_conditions[condition] = compile(_value, self.name, "eval")
                except Exception as e:
                    logging.error(f"python condition from type {self.name} compliation failure: {e}")
                    self.compiled_conditions[condition] = False

            # if we failed to compile then the condition fails
            if not self.compiled_conditions[condition]:
                return False

            try:
                # on two local variables are available to the python snippit:
                # observable and analysis module type
                return bool(
                    eval(
                        self.compiled_conditions[condition],
                        {},
                        {
                            "observable": observable,
                            "amt": self,
                        },
                    )
                )
            except Exception as e:
                logging.error(f"python condition from type {self.name} failed to execute: {e}")
                return False


class Analysis(TaggableObject, DetectableObject, MergableObject, Lockable):
    """Represents an output of analysis work."""

    def __init__(
        self,
        *args,
        details=None,
        type=None,
        root=None,
        observable=None,
        summary=None,
        error_message=None,
        stack_trace=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        assert root is None or isinstance(root, RootAnalysis)
        assert type is None or isinstance(type, AnalysisModuleType)
        assert observable is None or isinstance(observable, Observable)
        assert summary is None or isinstance(summary, str)
        assert error_message is None or isinstance(error_message, str)
        assert stack_trace is None or isinstance(stack_trace, str)

        # unique ID
        self.uuid: str = str(uuid.uuid4())

        # a reference to the RootAnalysis object this analysis belongs to
        self.root: Optional[RootAnalysis] = root

        # the type of analysis this is
        self.type: Optional[AnalysisModuleType] = type

        # list of Observables generated by this Analysis
        self.observable_ids = []

        # free form details of the analysis
        self._details = None

        # state tracker for when the details are modified
        self._details_modified = False

        # state tracker for when details are loaded
        self._details_loaded = False

        # if we passed the details in on the constructor then we set it here
        # which also updates the _details_modified
        if details:
            self.details = details

        # the observable this Analysis is for
        self.observable_id = observable.uuid if observable else None

        # a brief (or brief-ish summary of what the Analysis produced)
        # the idea here is that the analyst can read this summary and get
        # a pretty good idea of what was discovered without needing to
        # load all the details of the alert
        self._summary = summary or None

        # if analysis failed then this contains the description of the error
        # and a stack trace for debugging
        self.error_message = error_message
        self.stack_trace = stack_trace

    #
    # Lockable interface
    #

    @property
    def lock_id(self):
        return self.uuid

    # --------------------------------------------------------------------------------

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
    def details(self):
        # do we already have the details loaded or set?
        if self._details is not None:
            return self._details

        # load the external details and return those results
        self._load_details()
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

    #
    # json serialization
    #

    def to_model(self, *args, exclude_analysis_details=False, **kwargs) -> AnalysisModel:
        return AnalysisModel(
            tags=self.tags,
            detections=[DetectionPointModel(**_.to_dict(*args, **kwargs)) for _ in self.detections],
            uuid=self.uuid,
            type=None if self.type is None else AnalysisModuleTypeModel(**self.type.to_dict()).dict(),
            observable_id=self.observable_id,
            observable_ids=self.observable_ids,
            summary=self.summary,
            details=None if exclude_analysis_details else self._details,
            error_message=self.error_message,
            stack_trace=self.stack_trace,
        )

    def to_dict(self, *args, **kwargs) -> dict:
        return self.to_model(*args, **kwargs).dict()

    def to_json(self, *args, **kwargs) -> str:
        return self.to_model(*args, **kwargs).json()

    @staticmethod
    def from_dict(
        value: dict, root: "RootAnalysis", analysis: Optional["Analysis"] = None, _cls_map=None
    ) -> "Analysis":
        assert isinstance(value, dict)
        assert isinstance(root, RootAnalysis)
        assert analysis is None or isinstance(analysis, Analysis)

        if _cls_map is None:
            _cls_map = default_cls_map()

        result = analysis or _cls_map["Analysis"](root=root)
        result = TaggableObject.from_dict(value, result)
        result = DetectableObject.from_dict(value, result)

        data = AnalysisModel(**value)

        if data.type:
            result.type = _cls_map["AnalysisModuleType"].from_dict(data.type.dict())

        # if value[Analysis.KEY_TYPE]:
        # result.type = AnalysisModuleType.from_dict(value[Analysis.KEY_TYPE])

        # NOTE this is just a list of the Observable.uuid values (see to_dict())
        # we can't load them yet because the root would still be loading as all the observables expand

        result.observable_ids = data.observable_ids
        result.observable_id = data.observable_id

        result.summary = data.summary
        # result.iocs = value[Analysis.KEY_IOCS]
        result.uuid = data.uuid

        if data.details is not None:
            result._details = data.details
            result._details_loaded = False
            result._details_modified = True  # XXX ??? I think this is right

        result.error_message = data.error_message
        result.stack_trace = data.stack_trace

        result.root = root
        return result

    @staticmethod
    def from_json(value: str, root: "RootAnalysis", analysis: Optional["Analysis"] = None, _cls_map=None) -> "Analysis":
        assert isinstance(value, str)
        if _cls_map is None:
            _cls_map = default_cls_map()

        return _cls_map["Analysis"].from_dict(AnalysisModel.parse_raw(value).dict(), root, analysis, _cls_map=_cls_map)

    # =========================================================================

    @property
    def observable(self):
        """The Observable this Analysis is for (or None if this is an Alert.)"""
        if self.observable_id is None:
            return None

        return self.root.observable_store[self.observable_id]

    @observable.setter
    def observable(self, value):
        assert value is None or isinstance(value, Observable)
        self.observable_id = value.uuid if value is not None else None

    @property
    def observables(self):
        """A list of Observables that was generated by this Analysis.  These are references to the Observables to Alert.observables."""
        # at run time this is a list of Observable objects which are references to what it stored in the Alert.observable_store
        # when serialized to JSON this becomes a list of uuids (keys to the Alert.observable_store dict)
        return [self.root.observable_store[_] for _ in self.observable_ids]

    @observables.setter
    def observables(self, value):
        assert isinstance(value, list)
        self.observable_ids = [_.uuid for _ in value]

    def has_observable(self, o_or_o_type=None, o_value=None):
        """Returns True if this Analysis has this Observable.  Accepts a single Observable or o_type, o_value."""
        from ace.system.observables import create_observable

        if isinstance(o_or_o_type, Observable):
            return o_or_o_type in self.observables
        else:
            return create_observable(o_or_o_type, o_value) in self.observables

    @property
    def children(self):
        """Returns what is considered all of the "children" of this object (in this case is the the Observables.)"""
        return self.observables

    @property
    def observable_types(self):
        """Returns the list of unique observable types for all Observables generated by this Analysis."""
        return list(set([o.type for o in self.observables]))

    def get_observables_by_type(self, o_type):
        """Returns the list of Observables that match the given type."""
        return [o for o in self.observables if o.type == o_type]

    def get_observable_by_type(self, o_type):
        """Returns the first Observable of type o_type, or None if no Observable of that type exists."""
        result = self.get_observables_by_type(o_type)
        if len(result) == 0:
            return None

        return result[0]

    def find_observable(self, criteria):
        """Returns the first observable that matches the criteria, or None if nothing is found.

        param:criteria Must be one of the following:
        * a callable that takes a single :class:`Observable` as a parameter and returns a boolean
        * an indicator type (str)

        return: the first observable that matches the criteria, or None if nothing is found."""

        return self._find_observables(criteria, self.observables, single=True)

    def find_observables(self, criteria):
        """Same as :meth:`find_observable` but returns all observables found that match the criteria."""
        return self._find_observables(criteria, self.observables, single=False)

    def _find_observables(self, criteria, target_list, single=False):
        result = []
        for observable in target_list:
            if callable(criteria):
                if criteria(observable):
                    if single:
                        return observable
                    result.append(observable)
            else:
                if observable.type == criteria:
                    if single:
                        return observable
                    result.append(observable)

        if single:
            return None

        return result

    @property
    def summary(self):
        return self._summary

    @summary.setter
    def summary(self, value):
        self._summary = value

    def apply_merge(self, target: "Analysis") -> "Analysis":
        assert isinstance(target, Analysis)

        TaggableObject.apply_merge(self, target)
        DetectableObject.apply_merge(self, target)

        for observable in target.observables:
            existing_observable = self.root.get_observable(observable)
            if not existing_observable:
                # add any missing observables
                existing_observable = self.add_observable(observable.type, observable.value, time=observable.time)
            else:
                existing_observable = self.add_observable(existing_observable)

            # merge existing observables
            existing_observable.apply_merge(observable)

        # we don't need to merge this because it should already be merged
        # if target.observable:
        # existing_observable = self.root.get_observable(target.observable)
        # if existing_observable:
        # merge existing observables
        # existing_observable.apply_merge(target.observable)

        # self.observable = existing_observable

        return self

    # NOTE here that the "before" is a RootAnalysis object while the "after" is an Analysis object
    # Analysis objects don't have "before" and "after" because they don't exist until they are requested
    # however, when iterating through all the observables that were added to the resulting Analysis
    # a reference to the original RootAnalysis is required to get the original observable to compute the delta
    def apply_diff_merge(self, before: "RootAnalysis", after: "Analysis"):
        TaggableObject.apply_merge(self, after)
        DetectableObject.apply_merge(self, after)

        for after_observable in after.observables:
            # do we already have this observable?
            target_observable = self.root.get_observable(after_observable)
            if not target_observable:
                # if not then we add it to our analysis
                # NOTE that we make a new one here so that pre-existing and unrelated analysis is not copied over
                target_observable = self.add_observable(
                    after_observable.type, after_observable.value, time=after_observable.time
                )
            else:
                # otherwise we make sure this observable is added to our analysis now
                target_observable = self.add_observable(target_observable)

            # did this observable exist before analysis?
            before_observable = before.get_observable(after_observable)
            if not before_observable:
                # if not then just apply it
                target_observable.apply_merge(after_observable)
            else:
                # otherwise we apply the changes made to it
                # NOTE that we do not specify a type here
                target_observable.apply_diff_merge(before_observable, after_observable)

    def add_observable(self, o_or_o_type: Union[Observable, str], *args, **kwargs) -> "Observable":
        """Adds the Observable to this Analysis.  Returns the Observable object, or the one that already existed."""
        from ace.system.observables import create_observable

        assert isinstance(o_or_o_type, Observable) or isinstance(o_or_o_type, str)

        # if we passed a string as the first parameter then it's the type
        if isinstance(o_or_o_type, str):
            observable = create_observable(o_or_o_type, *args, **kwargs)
        else:
            observable = o_or_o_type

        # this may return an existing observable if we already have it
        observable = self.root.record_observable(observable)

        # add it to this Analysis object
        if observable.uuid not in self.observable_ids:
            self.observable_ids.append(observable.uuid)

        return observable

    def add_file(self, path: str, **kwargs) -> "Observable":
        """Utility function that adds a file observable to the root analysis by passing a path to the file."""
        from ace.system.storage import store_file

        return self.add_observable("file", store_file(path, roots=[self.uuid], **kwargs))

    def __str__(self):
        return f"Analysis({self.uuid},{self.type},{self.observable})"

    # this is used to sort in the GUI
    def __lt__(self, other):
        if not isinstance(other, Analysis):
            return False

        self_str = self.summary if self.summary is not None else str(self)
        other_str = other.summary if other.summary is not None else str(other)

        return self_str < other_str

    def __eq__(self, other):
        if type(self) is not type(other):
            return False

        # if they have the same uuid then they refer to the same analysis
        if self.uuid == other.uuid:
            return True

        # otherwise two Analysis objects are equal if they have the same amt and observable
        return self.type == other.type and self.observable == other.observable


class Observable(TaggableObject, DetectableObject, MergableObject):
    """Represents a piece of information discovered in an analysis that can itself be analyzed."""

    def __init__(
        self,
        type: str = None,
        value: str = None,
        time: Union[datetime.datetime, str, None] = None,
        root: Optional["RootAnalysis"] = None,
        directives: Optional[list[str]] = None,
        redirection: Optional[Observable] = None,
        links: Optional[list[str]] = None,
        limited_analysis: Optional[list[str]] = None,
        excluded_analysis: Optional[list[str]] = None,
        requested_analysis: Optional[list[str]] = None,
        relationships: Optional[dict[str, str]] = None,
        *args,
        **kwargs,
    ):

        super().__init__(*args, **kwargs)

        self.uuid = str(uuid.uuid4())
        self._type = type
        self.value = value
        self._time = time
        self._analysis = {}
        self._directives = directives or []  # of str
        self._redirection = redirection or None  # (str)
        self._links = links or []  # [ str ]
        self._limited_analysis = limited_analysis or []  # [ str ]
        self._excluded_analysis = excluded_analysis or []  # [ str ]
        self._requested_analysis = requested_analysis or []  # [ str ]
        self._relationships = relationships or {}  # key = name, value = [ Observable.uuid ]
        self._grouping_target = False
        self._request_tracking = {}  # key = AnalysisModuleType.name, value = AnalysisRequest.id

        # reference to the RootAnalysis object
        self.root = root

    def track_analysis_request(self, ar: "ace.system.analysis_request.AnalysisRequest"):
        """Tracks the request for analyze this Observable for the given type of analysis."""
        from ace.system.analysis_request import AnalysisRequest

        assert isinstance(ar, AnalysisRequest)

        logging.debug(f"tracking analysis request {ar} for {self}")
        self.request_tracking[ar.type.name] = ar.id

    # XXX not sure we use this
    def matches(self, value):
        """Returns True if the given value matches this value of this observable.  This can be overridden to provide more advanced matching such as CIDR for ipv4."""
        return self.value == value

    #
    # json serialization
    #

    def to_model(self, *args, **kwargs) -> ObservableModel:
        return ObservableModel(
            tags=self.tags,
            detections=[DetectionPointModel(**_.to_dict(*args, **kwargs)) for _ in self.detections],
            uuid=self.uuid,
            type=self.type,
            value=self.value,
            time=self.time,
            analysis={
                name: AnalysisModel(**analysis.to_dict(*args, **kwargs)).dict()
                for name, analysis in self.analysis.items()
            },
            directives=self.directives,
            redirection=self.redirection,
            links=self.links,
            limited_analysis=self.limited_analysis,
            excluded_analysis=self.excluded_analysis,
            requested_analysis=self.requested_analysis,
            relationships=self.relationships,
            grouping_target=self.grouping_target,
            request_tracking=self.request_tracking,
        )

    def to_dict(self, *args, **kwargs) -> dict:
        return self.to_model(*args, **kwargs).dict()

    def to_json(self, *args, **kwargs) -> str:
        return self.to_model(*args, **kwargs).json()

    @staticmethod
    def from_dict(
        value: dict, root: "RootAnalysis", observable: Optional["Observable"] = None, _cls_map=None
    ) -> "Observable":
        assert isinstance(value, dict)
        assert isinstance(root, RootAnalysis)
        assert observable is None or isinstance(observable, Observable)

        if _cls_map is None:
            _cls_map = default_cls_map()

        data = ObservableModel(**value)

        from ace.system.observables import create_observable

        observable = observable or create_observable(data.type, data.value, root=root)
        observable = TaggableObject.from_dict(value, observable)
        observable = DetectableObject.from_dict(value, observable)

        observable.uuid = data.uuid
        observable.type = data.type
        observable.time = data.time
        observable.value = data.value
        observable.analysis = {
            key: _cls_map["Analysis"].from_dict(analysis.dict(), root=root) for key, analysis in data.analysis.items()
        }
        observable.directives = data.directives
        observable._redirection = data.redirection
        observable.links = data.links
        observable.limited_analysis = data.limited_analysis
        observable.excluded_analysis = data.excluded_analysis
        observable.requested_analysis = data.requested_analysis
        observable.relationships = data.relationships
        observable.grouping_target = data.grouping_target
        observable.request_tracking = data.request_tracking

        return observable

    @staticmethod
    def from_json(
        value: str, root: "RootAnalysis", observable: Optional["Observable"] = None, _cls_map=None
    ) -> "Observable":
        assert isinstance(value, str)
        if _cls_map is None:
            _cls_map = default_cls_map()

        return _cls_map["Observable"].from_dict(
            ObservableModel.parse_raw(value).dict(), root, observable, _cls_map=_cls_map
        )

    # ========================================================================

    @property
    def type(self) -> str:
        return self._type

    @type.setter
    def type(self, value: str):
        assert isinstance(value, str)
        self._type = value

    @property
    def value(self) -> str:
        return self._value

    @value.setter
    def value(self, value: str):
        assert isinstance(value, str)
        self._value = value

    @property
    def time(self) -> Union[datetime.datetime, None]:
        return self._time

    @time.setter
    def time(self, value: Union[datetime.datetime, str, None]):
        if value is None:
            self._time = None
        elif isinstance(value, datetime.datetime):
            # if we didn't specify a timezone then we use the timezone of the local system
            if value.tzinfo is None:
                value = ace.LOCAL_TIMEZONE.localize(value)
            self._time = value
        elif isinstance(value, str):
            self._time = parse_datetime_string(value)
        else:
            raise ValueError(
                "time must be a datetime.datetime object or a string in the format "
                "%Y-%m-%d %H:%M:%S %z but you passed {}".format(type(value).__name__)
            )

    @property
    def directives(self) -> list[str]:
        return self._directives

    @directives.setter
    def directives(self, value: list[str]):
        assert isinstance(value, list)
        self._directives = value

    def add_directive(self, directive: str):
        """Adds a directive that analysis modules might use to change their behavior."""
        assert isinstance(directive, str)
        if directive not in self.directives:
            self.directives.append(directive)
            logging.debug(f"added directive {directive} to {self}")

        return self

    def has_directive(self, directive: str) -> bool:
        """Returns True if this Observable has this directive."""
        return directive in self.directives

    @property
    def redirection(self) -> Union[Observable, None]:
        if not self._redirection:
            return None

        return self.root.observable_store[self._redirection]

    @redirection.setter
    def redirection(self, value: Observable):
        assert isinstance(value, Observable)
        self._redirection = value.uuid

    @property
    def links(self):
        if not self._links:
            return []

        return [self.root.observable_store[_id] for _id in self._links]

    @links.setter
    def links(self, value):
        assert isinstance(value, list)
        self._links = [x.uuid for x in value]

    def add_link(self, target):
        """Links this Observable object to another Observable object.  Any tags
        applied to this Observable are also applied to the target Observable."""

        assert isinstance(target, Observable)

        # two observables cannot link to each other
        # that would cause a recursive loop in add_tag override
        if self in target.links:
            raise ValueError("{target} already links to {self}")

        if target.uuid not in self._links:
            self._links.append(target.uuid)

        logging.debug("linked {} to {}".format(self, target))

    @property
    def limited_analysis(self):
        return self._limited_analysis

    @limited_analysis.setter
    def limited_analysis(self, value):
        assert isinstance(value, list)
        assert all([isinstance(x, str) for x in value])
        self._limited_analysis = value

    def limit_analysis(self, amt: Union[AnalysisModuleType, str]):
        """Limit the analysis of this observable to the analysis module type specified by type or name."""
        assert isinstance(amt, str) or isinstance(amt, AnalysisModuleType)

        if isinstance(amt, AnalysisModuleType):
            amt = amt.name

        if amt not in self._limited_analysis:
            self._limited_analysis.append(amt)

    @property
    def excluded_analysis(self) -> list[str]:
        """Returns a list of analysis modules types that are excluded from analyzing this Observable."""
        return self._excluded_analysis

    @excluded_analysis.setter
    def excluded_analysis(self, value: list[str]):
        assert isinstance(value, list)
        self._excluded_analysis = value

    def exclude_analysis(self, amt: Union[AnalysisModuleType, str]):
        """Directs the engine to avoid analyzing this Observabe with this AnalysisModuleType."""
        assert isinstance(amt, str) or isinstance(amt, AnalysisModuleType)

        if isinstance(amt, AnalysisModuleType):
            amt = amt.name

        if amt not in self.excluded_analysis:
            self.excluded_analysis.append(amt)

    @property
    def requested_analysis(self) -> list[str]:
        """Returns a list of analysis modules types that have been requested for this Observable."""
        return self._requested_analysis

    @requested_analysis.setter
    def requested_analysis(self, value: list[str]):
        assert isinstance(value, list)
        self._requested_analysis = value

    def is_excluded(self, amt: Union[AnalysisModuleType, str]) -> bool:
        """Returns True if this Observable has been excluded from analysis by this AnalysisModuleType."""
        assert isinstance(amt, str) or isinstance(amt, AnalysisModuleType)
        if isinstance(amt, AnalysisModuleType):
            amt = amt.name

        return amt in self.excluded_analysis

    def is_requested(self, amt: Union[AnalysisModuleType, str]):
        """Returns True if this Observable has requested analysis for the given type."""
        assert isinstance(amt, str) or isinstance(amt, AnalysisModuleType)
        if isinstance(amt, AnalysisModuleType):
            amt = amt.name

        return amt in self.requested_analysis

    def request_analysis(self, amt: Union[AnalysisModuleType, str]):
        """Requests that the given analysis module executes on this observable.
        This is used for analysis modules that are set to manual execution."""
        assert isinstance(amt, str) or isinstance(amt, AnalysisModuleType)

        if isinstance(amt, AnalysisModuleType):
            amt = amt.name

        if amt not in self.requested_analysis:
            self.requested_analysis.append(amt)

    #
    # relationships
    #

    @property
    def relationships(self) -> dict[str, list[Observable]]:
        return {
            type: [self.root.observable_store[_] for _ in observables]
            for type, observables in self._relationships.items()
        }

    @relationships.setter
    def relationships(self, value: dict[str, list[Observable]]):
        self._relationships = {type: [_.uuid for _ in observables] for type, observables in value}

    def has_relationship(self, type: str, observable: Optional["Observable"] = None) -> bool:
        if observable is None:
            return type in self.relationships

        try:
            return observable.uuid in self._relationships[type]
        except KeyError:
            return False

    def add_relationship(self, type: str, target: "Observable") -> "Observable":
        """Adds a relationship between this observable and the target observable."""
        assert isinstance(type, str)
        assert isinstance(target, Observable)

        if type not in self.relationships:
            self._relationships[type] = list()

        self._relationships[type].append(target.uuid)
        return self

    def get_relationships_by_type(self, type: str) -> list["Observable"]:
        """Returns the list of related observables by type."""
        return self.relationships.get(type, [])

    def get_relationship_by_type(self, type: str) -> "Observable":
        """Returns the first related observable by type, or None if there are no observables related in that way."""
        result = self.get_relationships_by_type(type)
        if not result:
            return None

        return result[0]

    #
    # GROUPING TARGETS
    #
    # When an AnalysisModule uses the observation_grouping_time_range configuration option, ACE will select a
    # single Observable to analyze that falls within that time range. ACE will then *also* set the grouping_target
    # property of that Observable to True.
    # Then the next time another AnalysisModule which also groups by time is looking for an Observable to analyze
    # out of a group of Observables, it will select the (first) one that has grouping_target set to True.
    # This is so that most of the Analysis for grouped targets go into the same Observable, so that they're not
    # all spread out in the graphical view.
    #

    @property
    def grouping_target(self):
        """Retruns True if this Observable has become a grouping target."""
        return self._grouping_target

    @grouping_target.setter
    def grouping_target(self, value):
        assert isinstance(value, bool)
        self._grouping_target = value

    #
    # REQUEST TRACKING
    #

    @property
    def request_tracking(self):
        return self._request_tracking

    @request_tracking.setter
    def request_tracking(self, value) -> dict:
        """Returns a dict that maps the AnalysisModuleType.name to the AnalysisRequest.uuid."""
        assert isinstance(value, dict)
        self._request_tracking = value

    def get_analysis_request_id(self, amt: Union[AnalysisModuleType, str]) -> Union[str, None]:
        """Returns the AnalysisRequest.uuid for the given analysis module type, or None if nothing is tracked yet."""
        assert isinstance(amt, AnalysisModuleType) or isinstance(amt, str)
        if isinstance(amt, AnalysisModuleType):
            amt = amt.name

        return self.request_tracking.get(amt, None)

    # we override add_tag to ensure that linked Observable objects also get the same tags
    def add_tag(self, *args, **kwargs):
        super().add_tag(*args, **kwargs)
        for target in self.links:
            target.add_tag(*args, **kwargs)

        return self

    @property
    def analysis(self):
        return self._analysis

    @analysis.setter
    def analysis(self, value):
        assert isinstance(value, dict)
        self._analysis = value

    @property
    def all_analysis(self):
        """Returns a list of an Analysis objects executed against this Observable."""
        return [a for a in self._analysis.values()]

    @property
    def children(self):
        """Returns what is considered all of the "children" of this object (in this case it is the Analysis.)"""
        return [a for a in self.all_analysis]

    @property
    def parents(self):
        """Returns a list of Analysis objects that have this Observable."""
        return [a for a in self.root.all_analysis if a and a.has_observable(self)]

    def add_analysis(self, *args, **kwargs):
        assert isinstance(self.root, RootAnalysis)

        # if we didn't pass an Analysis object then we assume the args are for the Analysis constructor
        if args and isinstance(args[0], Analysis):
            analysis = args[0]
        else:
            analysis = Analysis(*args, **kwargs)

        # the Analysis must have an associated AnalysisModuleType
        if analysis.type is None:
            raise ValueError("the type property of the Analysis object must be a valid AnalysisModuleType")

        # does this analysis already exist?
        if analysis.type.name in self.analysis:
            raise ValueError(f"analysis for {self} type {analysis.type} already set")

        # set the document root for this analysis
        analysis.root = self.root
        # set the source of the Analysis
        analysis.observable = self

        self.analysis[analysis.type.name] = analysis

        # and then make sure that all the observables in this Analysis are added to the root
        analysis_observables = []
        for target_observable in analysis.observables:
            observable = self.root.get_observable(target_observable)
            # have we not already added it?
            if not observable:
                observable = analysis.add_observable(target_observable)
            else:
                observable.apply_merge(target_observable)

            if observable:
                analysis_observables.append(observable)

        analysis.observables = analysis_observables

        logging.debug(f"added analysis {analysis} type {analysis.type} to observable {self}")
        return analysis

    def get_analysis(self, amt: Union[AnalysisModuleType, str]) -> Union[Analysis, None]:
        """Returns the Analysis of the given type for this Observable, or None."""
        assert isinstance(amt, AnalysisModuleType) or isinstance(amt, str)
        if isinstance(amt, AnalysisModuleType):
            amt = amt.name

        return self.analysis.get(amt, None)

    def analysis_completed(self, amt: Union[AnalysisModuleType, str]) -> bool:
        """Returns True if the analysis of the given type has been completed for this Observable."""
        assert isinstance(amt, AnalysisModuleType) or isinstance(amt, str)
        if isinstance(amt, AnalysisModuleType):
            amt = amt.name

        return self.get_analysis(amt) is not None

    def apply_merge(self, target: "Observable") -> "Observable":
        """Merge all the mergable properties of the target Observable into this observable."""
        assert isinstance(target, Observable)
        TaggableObject.apply_merge(self, target)
        DetectableObject.apply_merge(self, target)

        assert target.type == self.type
        assert target.value == self.value

        for directive in target.directives:
            self.add_directive(directive)

        if target.redirection:
            # get a reference to the local copy of the target observable
            local_observable = self.root.get_observable(target.redirection)
            if not local_observable:
                # if we can't get it then add it
                local_observable = self.root.add_observable(target.redirection)

            self.redirection = local_observable

        for link in target.links:
            # get a reference to the local copy of the target observable
            local_observable = self.root.get_observable(link)
            if not local_observable:
                # if we can't get it then add it
                local_observable = self.root.add_observable(link)

            self.add_link(local_observable)

        for amt in target.limited_analysis:
            self.limit_analysis(amt)

        for amt in target.excluded_analysis:
            self.exclude_analysis(amt)

        for r_type, observables in target.relationships.items():
            for observable in observables:
                # get a reference to the local copy of the target observable
                local_observable = self.root.get_observable(observable)
                if not local_observable:
                    # if we can't get it then add it
                    local_observable = self.root.add_observable(observable.type, observable.value, time=observable.time)

                self.add_relationship(r_type, local_observable)

        if target.grouping_target:
            self.grouping_target = target.grouping_target

        for tag in target.tags:
            self.add_tag(tag)

        for amt, analysis in target.analysis.items():
            existing_analysis = self.get_analysis(amt)
            if not existing_analysis:
                # add any missing analysis
                # NOTE that we create a new analysis here and then merge
                existing_analysis = self.add_analysis(type=analysis.type, root=self.root, details=analysis.details)

            # merge existing analysis
            existing_analysis.apply_merge(analysis)

        return self

    def apply_diff_merge(
        self, before: "Observable", after: "Observable", type: Optional[AnalysisModuleType] = None
    ) -> "Observable":
        """Merge all the mergable properties of the target Observable into this observable."""
        assert isinstance(before, Observable)
        assert isinstance(after, Observable)
        assert before.type == after.type == self.type
        assert before.value == after.value == self.value
        assert type is None or isinstance(type, AnalysisModuleType)

        TaggableObject.apply_diff_merge(self, before, after)
        DetectableObject.apply_diff_merge(self, before, after)

        for directive in after.directives:
            if directive not in before.directives:
                self.add_directive(directive)

        if after.redirection != before.redirection:
            # get a reference to the local copy of the target observable
            local_observable = self.root.get_observable(after.redirection)
            if not local_observable:
                # if we can't get it then add it
                local_observable = self.root.add_observable(after.redirection)

            self.redirection = local_observable

        for link in after.links:
            if link in before.links:
                continue

            # get a reference to the local copy of the target observable
            local_observable = self.root.get_observable(link)
            if not local_observable:
                # if we can't get it then add it
                local_observable = self.root.add_observable(link)

            self.add_link(local_observable)

        for amt in after.limited_analysis:
            if amt not in before.limited_analysis:
                self.limit_analysis(amt)

        for amt in after.excluded_analysis:
            if amt not in before.excluded_analysis:
                self.exclude_analysis(amt)

        for r_type, observables in after.relationships.items():
            for observable in observables:
                if before.has_relationship(r_type, observable):
                    continue

                # get a reference to the local copy of the target observable
                local_observable = self.root.get_observable(observable)
                if not local_observable:
                    # if we can't get it then add it
                    local_observable = self.root.add_observable(observable.type, observable.value, time=observable.time)

                self.add_relationship(r_type, local_observable)

        if before.grouping_target != after.grouping_target:
            self.grouping_target = after.grouping_target

        if type:
            after_analysis = after.get_analysis(type)
            if after_analysis:
                target_analysis = self.add_analysis(
                    type=type,
                    details=after_analysis.details,
                    summary=after_analysis.summary,
                    error_message=after_analysis.error_message,
                    stack_trace=after_analysis.stack_trace,
                )
                target_analysis.apply_diff_merge(before.root, after_analysis)

        return self

    def create_analysis_request(self, amt: AnalysisModuleType) -> "ace.system.analysis_request.AnalysisRequest":
        """Creates and returns a new ace.system.analysis_request.AnalysisRequest object from this Observable."""
        from ace.system.analysis_request import AnalysisRequest

        return AnalysisRequest(root=self.root, observable=self, type=amt)

    def __str__(self):
        if self.time is not None:
            return "{}({}@{})".format(self.type, self.value, self.time)
        else:
            return "{}({})".format(self.type, self.value)

    # XXX there is also a match function for this?
    def _compare_value(self, other_value):
        """Default implementation to compare the value of this observable to the value of another observable.
        By default does == comparison, can be overridden."""
        return self.value == other_value

    def __eq__(self, other):
        if not isinstance(other, Observable):
            return False

        # exactly the same?
        if other.uuid == self.uuid:
            return True

        if other.type != self.type:
            return False

        if self.time is not None or other.time is not None:
            return self.time == other.time and self._compare_value(other.value)
        else:
            return self._compare_value(other.value)

    def __lt__(self, other):
        if not isinstance(other, Observable):
            return False

        if other.type == self.type:
            return self.value < other.value

        return self.type < other.type


class RootAnalysis(Analysis, MergableObject):
    """Root analysis object."""

    DEFAULT_ALERT_TYPE = "default"
    DEFAULT_QUEUE = "default"
    DEFAULT_DESCRIPTION = "ACE Analysis"

    def __init__(
        self,
        tool=None,
        tool_instance=None,
        alert_type=None,
        desc=None,
        event_time=None,
        details=None,
        name=None,
        state=None,
        uuid=None,
        storage_dir=None,
        analysis_mode=None,
        queue=None,
        instructions=None,
        version=None,
        expires=None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        import uuid as uuidlib

        # we are the root
        self.root = self

        self.analysis_mode = analysis_mode
        if analysis_mode:
            self.analysis_mode = analysis_mode

        self._uuid = str(uuidlib.uuid4())  # default is new uuid
        if uuid:
            self.uuid = uuid

        self._version = None
        if version is not None:
            self.version = version

        self._tool = None
        if tool:
            self.tool = tool

        self._tool_instance = None
        if tool_instance:
            self.tool_instance = tool_instance

        self._alert_type = RootAnalysis.DEFAULT_ALERT_TYPE
        if alert_type:
            self.alert_type = alert_type

        self._queue = RootAnalysis.DEFAULT_QUEUE
        if queue:
            self.queue = queue

        self._description = RootAnalysis.DEFAULT_DESCRIPTION
        if desc:
            self.description = desc

        self._instructions = None
        if instructions:
            self.instructions = instructions

        self._event_time = None
        if event_time:
            self.event_time = event_time

        self._name = None
        if name:
            self.name = name

        self._details = None
        if details:
            self.details = details

        self._storage_dir = None
        if storage_dir:
            self.storage_dir = storage_dir

        self.state = {}
        if state:
            self.state = state

        # all of the Observables discovered during analysis go into the observable_store
        self._observable_store = {}  # key = uuid, value = Observable object

        # set to True to cancel any outstanding analysis for this root
        self._analysis_cancelled = False

        # the reason why the analysis was cancelled
        self._analysis_cancelled_reason = None

        # if this is set to True then this analyis will expire (be removed)
        # if is_expired() returns True (see is_expired()) for the criteria
        # the default is to not expire root analysis
        # for systems that perform detection operations you would want to set this to True
        self._expires = False
        if expires is not None:
            self.expires = expires

    #
    # json serialization
    #

    def to_model(self, *args, exclude_analysis_details=False, **kwargs) -> RootAnalysisModel:
        return RootAnalysisModel(
            tags=self.tags,
            detections=[
                DetectionPointModel(**_.to_dict(*args, exclude_analysis_details=exclude_analysis_details, **kwargs))
                for _ in self.detections
            ],
            uuid=self.uuid,
            type=None if self.type is None else AnalysisModuleTypeModel(**self.type.to_dict()).dict(),
            observable_id=self.observable_id,
            observable_ids=self.observable_ids,
            summary=self.summary,
            details=None if exclude_analysis_details else self._details,
            tool=self.tool,
            tool_instance=self.tool_instance,
            alert_type=self.alert_type,
            description=self.description,
            event_time=self.event_time,
            name=self.name,
            state=self.state,
            analysis_mode=self.analysis_mode,
            queue=self.queue,
            instructions=self.instructions,
            version=self.version,
            expires=self.expires,
            analysis_cancelled=self.analysis_cancelled,
            analysis_cancelled_reason=self.analysis_cancelled_reason,
            observable_store={
                id: ObservableModel(
                    **observable.to_dict(*args, exclude_analysis_details=exclude_analysis_details, **kwargs)
                ).dict()
                for id, observable in self.observable_store.items()
            },
        )

    def to_dict(self, *args, **kwargs) -> dict:
        return self.to_model(*args, **kwargs).dict()

    def to_json(self, *args, **kwargs) -> str:
        return self.to_model(*args, **kwargs).json()

    @staticmethod
    def from_dict(value: dict, _cls_map=None) -> "RootAnalysis":
        assert isinstance(value, dict)

        if _cls_map is None:
            _cls_map = default_cls_map()

        data = RootAnalysisModel(**value)

        root = _cls_map["RootAnalysis"]()
        root.observable_store = {
            # XXX should probably be using create_observable here, eh?
            id: _cls_map["Observable"].from_dict(observable.dict(), root=root)
            for id, observable in data.observable_store.items()
        }

        root = _cls_map["Analysis"].from_dict(value, root, analysis=root)

        root._analysis_mode = data.analysis_mode
        root._uuid = data.uuid
        root._version = data.version
        root._tool = data.tool
        root._tool_instance = data.tool_instance
        root._alert_type = data.alert_type
        root._description = data.description
        root._event_time = data.event_time
        root._name = data.name
        root._queue = data.queue
        root._instructions = data.instructions
        root._analysis_cancelled = data.analysis_cancelled
        root._analysis_cancelled_reason = data.analysis_cancelled_reason
        root._expires = data.expires
        root._state = data.state
        return root

    @staticmethod
    def from_json(value: str, _cls_map=None) -> "RootAnalysis":
        assert isinstance(value, str)
        if _cls_map is None:
            _cls_map = default_cls_map()

        return _cls_map["RootAnalysis"].from_dict(RootAnalysisModel.parse_raw(value).dict(), _cls_map=_cls_map)

    # ========================================================================

    @property
    def analysis_mode(self):
        return self._analysis_mode

    @analysis_mode.setter
    def analysis_mode(self, value):
        assert value is None or (isinstance(value, str) and value)
        self._analysis_mode = value

    @property
    def uuid(self):
        return self._uuid

    @uuid.setter
    def uuid(self, value):
        assert isinstance(value, str)
        self._uuid = value

    @property
    def version(self) -> int:
        """Returns the current version of this RootAnalysis object."""
        return self._version

    @version.setter
    def version(self, value: str):
        assert value is None or isinstance(value, str) and value
        self._version = value

    @property
    def tool(self):
        """The name of the tool that generated the alert (ex: splunk)."""
        return self._tool

    @tool.setter
    def tool(self, value):
        assert value is None or isinstance(value, str)
        self._tool = value

    @property
    def tool_instance(self):
        """The instance of the tool that generated the alert (ex: the hostname of the sensor)."""
        return self._tool_instance

    @tool_instance.setter
    def tool_instance(self, value):
        assert value is None or isinstance(value, str)
        self._tool_instance = value

    @property
    def alert_type(self):
        """The type of the alert (ex: splunk - ipv4 search)."""
        return self._alert_type

    @alert_type.setter
    def alert_type(self, value):
        assert value is None or isinstance(value, str)
        self._alert_type = value

    @property
    def queue(self):
        """The queue the alert will appear in (ex: external, internal)."""
        return self._queue

    @queue.setter
    def queue(self, value):
        assert isinstance(value, str)
        self._queue = value

    @property
    def instructions(self):
        """A free form string value that gives the analyst instructions on what
        this alert is about and/or how to analyze the data contained in the
        alert."""
        return self._instructions

    @instructions.setter
    def instructions(self, value):
        self._instructions = value

    @property
    def description(self):
        """A brief one line description of the alert (ex: high_pdf_xor_kernel32 match in email attachment)."""
        return self._description

    @description.setter
    def description(self, value):
        assert value is None or isinstance(value, str)
        self._description = value

    @property
    def event_time(self):
        """Returns a datetime object representing the time this event was created or occurred."""
        return self._event_time

    @event_time.setter
    def event_time(self, value):
        """Sets the event_time. Accepts a datetime object or a string in the format %Y-%m-%d %H:%M:%S %z."""
        if value is None:
            self._event_time = None
        elif isinstance(value, datetime.datetime):
            # if we didn't specify a timezone then we use the timezone of the local system
            if value.tzinfo is None:
                value = ace.LOCAL_TIMEZONE.localize(value)
            self._event_time = value
        elif isinstance(value, str):
            self._event_time = parse_datetime_string(value)
        else:
            raise ValueError(
                "event_time must be a datetime.datetime object or a string in the format "
                "%Y-%m-%d %H:%M:%S %z but you passed {}".format(type(value).__name__)
            )

    @property
    def expires(self) -> bool:
        """Returns True if this root should eventually expire."""
        return self._expires

    @expires.setter
    def expires(self, value: bool):
        assert isinstance(value, bool)
        self._expires = value

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

    # override the summary property of the Analysis object to reflect the description
    @property
    def summary(self):
        return self.description

    @summary.setter
    def summary(self, value):
        """This does nothing, but it does get called when you assign to the json property."""
        pass

    @property
    def observable_store(self):
        """Hash of the actual Observable objects generated during the analysis of this Alert.  key = uuid, value = Observable."""
        return self._observable_store

    @observable_store.setter
    def observable_store(self, value):
        assert isinstance(value, dict)
        self._observable_store = value

    @property
    def storage_dir(self):
        """The base storage directory for output."""
        return self._storage_dir

    @storage_dir.setter
    def storage_dir(self, value):
        assert value is None or isinstance(value, str)
        self._storage_dir = value

    def initialize_storage(self, path: Optional[str] = None) -> bool:
        """Initializes and creates a local storage directory if one does not
        already exist.  If the path is specified it is used as the storage
        directory, otherwise a temporary directory is created in ace.TEMP_DIR.
        """
        if self.storage_dir is None:
            if path:
                self.storage_dir = path
            else:
                # XXX get temp dir from config
                self.storage_dir = tempfile.mkdtemp()

        if not os.path.isdir(self.storage_dir):
            os.mkdir(self.storage_dir)

        return True

    @property
    def name(self):
        """An optional property that defines a name for an alert.
        Used to track and document analyst response instructions."""
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def analysis_cancelled(self) -> bool:
        """Returns True if analysis has been cancelled for this root."""
        return self._analysis_cancelled

    @analysis_cancelled.setter
    def analysis_cancelled(self, value: bool):
        assert isinstance(value, bool)
        self._analysis_cancelled = value

    @property
    def analysis_cancelled_reason(self) -> Union[str, None]:
        """Optional short description explaining why the cancellation was made."""
        return self._analysis_cancelled_reason

    @analysis_cancelled_reason.setter
    def analysis_cancelled_reason(self, value: Union[str, None]):
        assert value is None or isinstance(value, str)
        self._analysis_cancelled_reason = value

    def cancel_analysis(self, reason: Optional[str] = None):
        """Cancels any further analysis on this root. An optional reason can be supplied to document the action."""
        self.analysis_cancelled = True
        if reason:
            self.analysis_cancelled_reason = reason

    def record_observable(self, observable):
        """Records the given observable into the observable_store if it does not already exist.
        Returns the new one if recorded or the existing one if not."""
        assert isinstance(observable, Observable)

        # XXX gross this is probably pretty inefficient
        for o in self.observable_store.values():
            if o == observable:
                logging.debug(
                    "returning existing observable {} ({}) [{}] <{}> for {} ({}) [{}] <{}>".format(
                        o, id(o), o.uuid, o.type, observable, id(observable), observable.uuid, observable.type
                    )
                )
                return o

        observable.root = self
        self.observable_store[observable.uuid] = observable
        logging.debug("recorded observable {} with id {}".format(observable, observable.uuid))
        return observable

    def save(self) -> bool:
        """Tracks or updates this root. Returns True if successful, False otherwise."""
        from ace.system.analysis_tracking import track_root_analysis

        if not track_root_analysis(self):
            return False

        for analysis in self.all_analysis:
            if analysis is not self:
                analysis.save()

        # save our own details
        Analysis.save(self)
        return True

    def update(self) -> bool:
        """Loads and merges any changes made to this root. Returns True if successful, False otherwise."""
        from ace.system.analysis_tracking import get_root_analysis

        existing_root = get_root_analysis(self)
        if not existing_root:
            return False

        if self.version == existing_root.version:
            return False

        self.apply_merge(existing_root)
        self.version = existing_root.version
        return True

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

    def __str__(self):
        if self.storage_dir:
            return f"RootAnalysis({self.uuid}) @ {self.storage_dir}"
        else:
            return f"RootAnalysis({self.uuid})"

    def __eq__(self, other):
        """Two RootAnalysis objects are equal if the uuid is equal."""
        if not isinstance(other, type(self)):
            return False

        return other.uuid == self.uuid

    @property
    def all_analysis(self):
        """Returns the list of all Analysis performed for this Alert."""
        result = []
        result.append(self)
        for observable in self.observable_store.values():
            for analysis in observable.analysis.values():
                if analysis:
                    result.append(analysis)

        return result

    @property
    def all_observables(self):
        """Returns the list of all Observables discovered for this Alert."""
        return list(self.observable_store.values())

    def get_observables_by_type(self, o_type):
        """Returns the list of Observables that match the given type."""
        return [o for o in self.all_observables if o.type == o_type]

    def find_observable(self, criteria):
        return self._find_observables(criteria, self.all_observables, single=True)

    def find_observables(self, criteria):
        return self._find_observables(criteria, self.all_observables, single=False)

    @property
    def all(self):
        """Returns the list of all Observables and Analysis for this RootAnalysis."""
        result = self.all_analysis[:]
        result.extend(self.all_observables)
        return result

    @property
    def all_tags(self):
        """Return all unique tags for the entire Alert."""
        result = []
        for analysis in self.all_analysis:
            if analysis.tags is not None:
                result.extend(analysis.tags)
        for observable in self.all_observables:
            if observable.tags is not None:
                result.extend(observable.tags)

        return list(set(result))

    def get_all_references(self, target: Union[Observable, Analysis]):
        """Iterators through all objects that refer to target."""
        assert isinstance(target, Observable) or isinstance(target, Analysis)
        result = []
        if isinstance(target, Observable):
            for analysis in self.all_analysis:
                if target in analysis.observables:
                    result.append(analysis)
        elif isinstance(target, Analysis):
            for observable in self.all_observables:
                if target in observable.all_analysis:
                    result.append(observable)

        return result

    def get_observable(self, uuid_or_observable: Union[str, Observable]):
        """Returns the Observable object for the given uuid or None if the Observable does not exist."""
        assert isinstance(uuid_or_observable, str) or isinstance(uuid_or_observable, Observable)

        # if we passed the id of an Observable then we return that specific Observable or None if it does not exist
        if isinstance(uuid_or_observable, str):
            return self.observable_store.get(uuid_or_observable, None)

        observable = uuid_or_observable

        try:
            # if we passed an existing Observable (same id) then we return the reference inside the RootAnalysis
            # with the matching id
            return self.observable_store[observable.uuid]
        except KeyError:
            # otherwise we try to match based on the type, value and time
            return self.find_observable(
                lambda o: o.type == observable.type and o.value == observable.value and o.time == observable.time
            )

    @property
    def all_detection_points(self):
        """Returns all DetectionPoint objects found in any DetectableObject in the heiarchy."""
        result = []
        for a in self.all_analysis:
            result.extend(a.detections)
        for o in self.all_observables:
            result.extend(o.detections)

        return result

    def has_detections(self):
        """Returns True if this RootAnalysis could become an Alert (has at least one DetectionPoint somewhere.)"""
        if self.has_detection_points():
            return True
        for a in self.all_analysis:
            if a.has_detection_points():
                return True
        for o in self.all_observables:
            if o.has_detection_points():
                return True

    def create_analysis_request(self):
        """Creates and returns a new ace.system.analysis_request.AnalysisRequest object from this RootAnalysis."""
        from ace.system.analysis_request import AnalysisRequest

        return AnalysisRequest(self)

    def submit(self):
        """Submits this RootAnalysis for analysis."""
        from ace.system.analysis_request import submit_analysis_request

        return submit_analysis_request(self.create_analysis_request())

    def analysis_completed(self, observable: Observable, amt: AnalysisModuleType) -> bool:
        """Returns True if the given analysis has been completed for the given observable."""
        assert isinstance(observable, Observable)
        assert isinstance(amt, AnalysisModuleType)
        observable = self.get_observable(observable)
        if observable is None:
            raise UnknownObservableError(observable)

        return observable.analysis_completed(amt)

    def analysis_tracked(self, observable: Observable, amt: AnalysisModuleType) -> bool:
        """Returns True if the analysis for the given Observable and type is already requested (tracked.)"""
        assert isinstance(observable, Observable)
        assert isinstance(amt, AnalysisModuleType)

        observable = self.get_observable(observable)
        if observable is None:
            raise UnknownObservableError(observable)

        return observable.get_analysis_request_id(amt) is not None

    def apply_merge(self, target: "RootAnalysis") -> "RootAnalysis":
        """Merge all the mergable properties of the target RootAnalysis into this root."""
        assert isinstance(target, RootAnalysis)
        Analysis.apply_merge(self, target)

        # you cannot merge two different root analysis objects together
        if self.uuid != target.uuid:
            raise ValueError(f"attempting to merge a different RootAnalysis ({target}) into {self}")

        # merge any properties that can be modified after a RootAnalysis is created
        self.analysis_mode = target.analysis_mode
        self.queue = target.queue
        self.description = target.description
        self.analysis_cancelled = target.analysis_cancelled
        self.analysis_cancelled_reason = target.analysis_cancelled_reason
        # NOTE that we don't copy over the version data
        return self

    def apply_diff_merge(self, before: "RootAnalysis", after: "RootAnalysis") -> "RootAnalysis":
        assert isinstance(before, RootAnalysis)
        assert isinstance(after, RootAnalysis)

        if before.uuid != after.uuid:
            raise ValueError(f"attempting to apply diff merge against two difference roots {before} and {after}")

        TaggableObject.apply_diff_merge(self, before, after)
        DetectableObject.apply_diff_merge(self, before, after)

        if before.analysis_mode != after.analysis_mode:
            self.analysis_mode = after.analysis_mode

        if before.queue != after.queue:
            self.queue = after.queue

        if before.description != after.description:
            self.description = after.description

        if before.analysis_cancelled != after.analysis_cancelled:
            self.analysis_cancelled = after.analysis_cancelled

        if before.analysis_cancelled_reason != after.analysis_cancelled_reason:
            self.analysis_cancelled_reason = after.analysis_cancelled_reason

        return self


def recurse_down(target: Union[Analysis, Observable], callback):
    """Calls callback starting at target back to the RootAnalysis."""
    assert isinstance(target, Analysis) or isinstance(target, Observable)
    assert callable(callback)

    if target == target.root:
        callback(target)
        return

    visited = []  # keep track of what we've looked at
    root = target.root

    def _recurse(target, callback):
        nonlocal visited, root
        # make sure we haven't already looked at this one
        if target in visited:
            return

        callback(target)
        visited.append(target)

        # are we at the end?
        if target is root:
            return

        if isinstance(target, Observable):
            # find all Analysis objects that reference this Observable
            for analysis in root.get_all_references(target):
                _recurse(analysis, callback)

        elif isinstance(target, Analysis):
            if target.observable:
                _recurse(target.observable, callback)

    _recurse(target, callback)


def search_down(target: Union[Observable, Analysis], callback) -> Union[Observable, Analysis]:
    """Searches from target down to RootAnalysis looking for callback(obj) to return True."""
    assert isinstance(target, Observable) or isinstance(target, Analysis)
    assert callable(callback)
    result = None

    def _callback(target):
        nonlocal result
        if result:
            return

        if callback(target):
            result = target

    recurse_down(target, _callback)
    return result


# or "search_up" or "search_out"
def recurse_tree(target: Union[Observable, Analysis], callback):
    """A utility function to run the given callback on every Observable and
    Analysis rooted at the given Observable or Analysis object."""
    assert isinstance(target, Analysis) or isinstance(target, Observable)
    assert callable(callback)

    visited = []

    def _recurse(target, callback):
        nonlocal visited
        callback(target)
        visited.append(target)

        if isinstance(target, Analysis):
            for observable in target.observables:
                if observable not in visited:
                    _recurse(observable, callback)
        elif isinstance(target, Observable):
            for analysis in target.all_analysis:
                if analysis not in visited:
                    _recurse(analysis, callback)

    _recurse(target, callback)


def default_cls_map() -> dict:
    return {
        "Analysis": Analysis,
        "AnalysisModuleType": AnalysisModuleType,
        "Observable": Observable,
        "RootAnalysis": RootAnalysis,
    }
