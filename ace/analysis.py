# vim: sw=4:ts=4:et

import copy
import datetime
import hashlib
import json
import logging
import os
import os.path
import shutil
import sys
import time
import uuid

from dataclasses import dataclass, field
from typing import List, Union, Optional, Any

import ace
from ace.json import JSONEncoder
from ace.constants import *
from ace.error import report_exception
from ace.indicators import Indicator, IndicatorList
from ace.system.locking import Lockable

class MergableObject():
    """An object is mergable if a newer version of it can be merged into an older existing version."""
    def apply_merge(self, target: 'MergableObject') -> Union['MergableObject', None]:
        raise NotImplemented()

    def apply_diff_merge(self, before: 'MergableObject', after: 'MergableObject') -> Union['MergableObject', None]:
        raise NotImplemented()

class DetectionPoint():
    """Represents an observation that would result in a detection."""

    KEY_DESCRIPTION = 'description'
    KEY_DETAILS = 'details'

    def __init__(self, description=None, details=None):
        self.description = description
        self.details = details

    @property
    def json(self):
        return {
            DetectionPoint.KEY_DESCRIPTION: self.description,
            DetectionPoint.KEY_DETAILS: self.details, 
        }

    @json.setter
    def json(self, value):
        assert isinstance(value, dict)
        if DetectionPoint.KEY_DESCRIPTION in value:
            self.description = value[DetectionPoint.KEY_DESCRIPTION]
        if DetectionPoint.KEY_DETAILS in value:
            self.details = value[DetectionPoint.KEY_DETAILS]

    @staticmethod
    def from_json(dp_json):
        """Loads a DetectionPoint from a JSON dict. Used by _materalize."""
        dp = DetectionPoint()
        dp.json = dp_json
        return dp

    # XXX move to gui code
    @property
    def display_description(self):
        if isinstance(self.description, str):
            return self.description.encode('unicode_escape').decode()
        else:
            return self.description

    def __str__(self):
        return "DetectionPoint({})".format(self.description)

    def __eq__(self, other):
        if not isinstance(other, DetectionPoint):
            return False

        return self.description == other.description and self.details == other.details

class DetectableObject(MergableObject):
    """Mixin for objects that can have detection points."""

    KEY_DETECTIONS = 'detections'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._detections = []

    @property
    def json(self):
        return { DetectableObject.KEY_DETECTIONS: self._detections }

    @json.setter
    def json(self, value):
        assert isinstance(value, dict)
        if DetectableObject.KEY_DETECTIONS in value:
            self._detections = value[DetectableObject.KEY_DETECTIONS]

    @property
    def detections(self):
        return self._detections

    @detections.setter
    def detections(self, value):
        assert isinstance(value, list)
        assert all([isinstance(x, DetectionPoint) for x in value]) or all([isinstance(x, dict) for x in value])
        self._detections = value

    def has_detection_points(self):
        """Returns True if this object has at least one detection point, False otherwise."""
        return len(self._detections) != 0

    def add_detection_point(self, description_or_detection: Union[DetectionPoint, str], details: Optional[str]=None) -> 'DetectableObject':
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

    def apply_merge(self, target: 'DetectableObject') -> 'DetectableObject':
        assert isinstance(target, DetectableObject)
        for detection in target.detections:
            self.add_detection_point(detection)

        return self

    def apply_diff_merge(self, before: 'DetectableObject', after: 'DetectableObject') -> 'DetectableObject':
        assert isinstance(before, DetectableObject)
        assert isinstance(after, DetectableObject)
        for detection in after.detections:
            if detection not in before.detections:
                self.add_detection_point(detection)

        return self

class TaggableObject(MergableObject):
    """A mixin class that adds a tags property that is a list of tags assigned to this object."""

    KEY_TAGS = 'tags'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # list of strings 
        self._tags = []

    @property
    def json(self):
        return {
            TaggableObject.KEY_TAGS: self.tags
        }

    @json.setter
    def json(self, value):
        assert isinstance(value, dict)
        if TaggableObject.KEY_TAGS in value:
            self.tags = value[TaggableObject.KEY_TAGS]

    @property
    def tags(self):
        return self._tags

    @tags.setter
    def tags(self, value):
        assert isinstance(value, list)
        assert all([isinstance(i, str) for i in value])
        self._tags = value

    def add_tag(self, tag: str) -> 'TaggableObject':
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

    def apply_merge(self, target: 'TaggableObject') -> 'TaggableObject':
        assert isinstance(target, TaggableObject)

        for tag in target.tags:
            self.add_tag(tag)

        return self

    def apply_diff_merge(self, before: 'TaggableObject', after: 'TaggableObject') -> 'TaggableObject':
        assert isinstance(before, TaggableObject)
        assert isinstance(after, TaggableObject)

        for tag in after.tags:
            if tag not in before.tags:
                self.add_tag(tag)

        return self

# forward declaraction
class Observable:
    pass

@dataclass
class AnalysisModuleType():
    """Represents a registration of an analysis module type."""

    # the name of the analysis module type
    name: str
    # brief English description of what the module does
    description: str
    # list of supported observable types (empty list supports all observable)
    observable_types: List[str] = field(default_factory=list)
    # list of required directives (empty list means no requirement)
    directives: List[str] = field(default_factory=list)
    # list of other analysis module type names to wait for (empty list means no deps)
    dependencies: List[str] = field(default_factory=list)
    # list of required tags (empty list means no requirement)
    tags: List[str] = field(default_factory=list)
    # list of valid analysis modes
    modes: List[str] = field(default_factory=list)
    # the current version of the analysis module type
    version: str = '1.0.0'
    # how long this analysis module has before it times out (in seconds)
    # by default it takes the global default specified in the configuration file
    # you can set a very high timeout but nothing can never timeout
    timeout: int = 30
    # how long analysis results stay in the cache (in seconds)
    # a value of None means it is not cached
    cache_ttl: Optional[int] = None
    # what additional values should be included to determine the cache key?
    additional_cache_keys: List[str] = field(default_factory=list)
    # what kind of analysis module does this classify as?
    # examples: [ 'sandbox' ], [ 'splunk' ], etc...
    types: List[str] = field(default_factory=list)

    def version_matches(self, amt) -> bool:
        """Returns True if the given amt is the same version as this amt."""
        return ( 
                self.name == amt.name and
                self.version == amt.version and
                sorted(self.additional_cache_keys) == sorted(amt.additional_cache_keys) )
        # XXX should probably check the other fields as well

    def to_dict(self):
        return {
            'name': self.name,
            'description': self.name,
            'observable_types': self.observable_types,
            'directives': self.directives,
            'dependencies': self.dependencies,
            'tags': self.tags,
            'modes': self.modes,
            'version': self.version,
            'timeout': self.timeout,
            'cache_ttl': self.cache_ttl,
            'additional_cache_keys': self.additional_cache_keys,
        }

    @staticmethod
    def from_dict(value: dict):
        return AnalysisModuleType(
            name = value['name'],
            description = value['description'],
            observable_types = value['observable_types'],
            directives = value['directives'],
            dependencies = value['dependencies'],
            tags = value['tags'],
            modes = value['modes'],
            version = value['version'],
            timeout = value['timeout'],
            cache_ttl = value['cache_ttl'],
            additional_cache_keys = value['additional_cache_keys'],
        )

    def accepts(self, observable: Observable) -> bool:
        from ace.system.analysis_module import get_analysis_module_type
        assert isinstance(observable, Observable)

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

class Analysis(TaggableObject, DetectableObject, MergableObject, Lockable):
    """Represents an output of analysis work."""

    # dictionary keys used by the Analysis class
    KEY_OBSERVABLES = 'observables'
    KEY_DETAILS = 'details'
    KEY_SUMMARY = 'summary'
    KEY_TYPE = 'type'
    KEY_UUID = 'uuid'
    KEY_IOCS = 'iocs'

    def __init__(self, *args, details=None, type=None, root=None, observable=None, summary=None, **kwargs):
        super().__init__(*args, **kwargs)
        assert root is None or isinstance(root, RootAnalysis)
        assert type is None or isinstance(type, AnalysisModuleType)
        assert observable is None or isinstance(observable, Observable)
        assert summary is None or isinstance(summary, str)

        # unique ID
        self.uuid: str = str(uuid.uuid4())

        # a reference to the RootAnalysis object this analysis belongs to 
        self.root: Optional[RootAnalysis] = root

        # the type of analysis this is
        self.type: Optional[AnalysisModuleType] = type

        # list of Observables generated by this Analysis
        self._observables = []

        # free form details of the analysis
        self._details = None

        # state tracker for when the details are modified
        self._details_modified = False

        # if we passed the details in on the constructor then we set it here
        # which also updates the _details_modified
        if details:
            self.details = details

        # the observable this Analysis is for
        self._observable = observable

        # a brief (or brief-ish summary of what the Analysis produced)
        # the idea here is that the analyst can read this summary and get
        # a pretty good idea of what was discovered without needing to
        # load all the details of the alert
        self._summary = summary or None

        # List of IOCs that the analysis contains
        self._iocs = IndicatorList()

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

    # XXX refactor for ace.system
    def reset(self):
        """Deletes the current analysis output if it exists."""
        logging.debug("called reset() on {}".format(self))
        if self.external_details_path is not None:
            full_path = abs_path(os.path.join(self.root.storage_dir, '.ace', self.external_details_path))
            if os.path.exists(full_path):
                logging.debug("removing external details file {}".format(full_path))
                os.remove(full_path)
            else:
                logging.warning("external details path {} does not exist".format(full_path))

        self._details = None
        self.external_details_path = None
        self.external_details = None

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
            report_exception()

    @property
    def json(self):
        result = TaggableObject.json.fget(self)
        result.update(DetectableObject.json.fget(self))
        result.update({
            Analysis.KEY_TYPE: self.type.to_dict() if self.type else None,
            Analysis.KEY_OBSERVABLES: [o.id for o in self.observables],
            TaggableObject.KEY_TAGS: self.tags,
            Analysis.KEY_SUMMARY: self.summary,
            Analysis.KEY_IOCS: self.iocs.json,
            Analysis.KEY_UUID: self.uuid,
        })
        return result

    def to_dict(self) -> dict:
        return self.json

    @json.setter
    def json(self, value):
        assert isinstance(value, dict)
        TaggableObject.json.fset(self, value)
        DetectableObject.json.fset(self, value)

        if Analysis.KEY_TYPE in value:
            if value[Analysis.KEY_TYPE]:
                self.type = AnalysisModuleType.from_dict(value[Analysis.KEY_TYPE])

        if Analysis.KEY_OBSERVABLES in value:
            # and then we un-serialize them back when we load from JSON
            self.observables = value[Analysis.KEY_OBSERVABLES]

        self.details = None

        if Analysis.KEY_SUMMARY in value:
            self.summary = value[Analysis.KEY_SUMMARY]

        if Analysis.KEY_IOCS in value:
            self.iocs = value[Analysis.KEY_IOCS]

        if Analysis.KEY_UUID in value:
            self.uuid = value[Analysis.KEY_UUID]

    @staticmethod
    def from_dict(json_dict: dict) -> 'Analysis':
        analysis = Analysis()
        analysis.json = json_dict
        return analysis

    @property
    def iocs(self):
        return self._iocs

    @iocs.setter
    def iocs(self, value):
        assert isinstance(value, list)
        self._iocs = IndicatorList()
        for i in value:
            self._iocs.append(i)

    @property
    def observables(self):
        """A list of Observables that was generated by this Analysis.  These are references to the Observables to Alert.observables."""
        # at run time this is a list of Observable objects which are references to what it stored in the Alert.observable_store
        # when serialized to JSON this becomes a list of uuids (keys to the Alert.observable_store dict)
        return self._observables

    @observables.setter
    def observables(self, value):
        assert isinstance(value, list)
        assert all(isinstance(o, str) or isinstance(o, Observable) for o in self._observables)
        self._observables = value

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

    def _load_observable_references(self):
        """Utility function to replace uuid strings in Analysis.observables with references to Observable objects in Alert.observable_store."""
        assert isinstance(self.root, RootAnalysis)

        _buffer = []
        for uuid in self._observables:
            if uuid not in self.root.observable_store:
                logging.warning(f"missing observable with uuid {uuid} in {self.root}")
            else:
                _buffer.append(self.root.observable_store[uuid])

        self._observables = _buffer

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
    def observable(self):
        """The Observable this Analysis is for (or None if this is an Alert.)"""
        return self._observable

    @observable.setter
    def observable(self, value):
        assert value is None or isinstance(value, Observable)
        self._observable = value

    @property
    def summary(self):
        return self._summary

    @summary.setter
    def summary(self, value):
        self._summary = value

    def search_tree(self, tags=()):
        """Searches this object and every object in it's analysis tree for the given items.  Returns the list of items that matched."""

        if not isinstance(tags, tuple):
            tags = (tags,)

        result = []
        def _search(target):
            for tag in tags:
                if target.has_tag(tag):
                    if target not in result:
                        result.append(target)

        recurse_tree(self, _search)
        return result

    def merge(self, target: 'Analysis') -> 'Analysis':
        TaggableObject.apply_merge(self, target)
        DetectableObject.apply_merge(self, target)

        for observable in target.observables:
            existing_observable = self.root.get_observable(observable)
            if not existing_observable:
                # add any missing observables
                self.add_observable(observable)
            else:
                # merge existing observables
                existing_observable.apply_merge(observable)

        return self

    def add_observable(self, o_or_o_type: Union[Observable, str], *args, **kwargs) -> 'Observable':
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
        if observable not in self.observables:
            self.observables.append(observable)

        return observable

    def add_file(self, path: str, **kwargs) -> 'FileObservable':
        """Utility function that adds a F_FILE observable to the root analysis by passing a path to the file."""
        from ace.system.storage import store_file
        return self.add_observable(F_FILE, store_file(path, roots=[self.uuid], **kwargs))

    def add_ioc(self, type_: str, value: str, status: str = 'New', tags: List[str] = []):
        self.iocs.append(Indicator(type_, value, status=status, tags=tags))

    def __str__(self):
        return f'Analysis({self.uuid},{self.type},{self.observable})'

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

    def __hash__(self):
        return hash(self.summary)

    ##########################################################################
    # OVERRIDABLES 

class Relationship(object):
    """Represents a relationship to another object."""
    KEY_RELATIONSHIP_TYPE = 'type'
    KEY_RELATIONSHIP_TARGET = 'target'

    def __init__(self, r_type=None, target=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._r_type = r_type
        self._target = target

    def __str__(self):
        return "Relationship({} -> {})".format(self.r_type, self.target)

    def __repr__(self):
        return str(self)

    @property
    def r_type(self):
        return self._r_type
    
    @r_type.setter
    def r_type(self, value):
        assert value in VALID_RELATIONSHIP_TYPES
        self._r_type = value

    @property
    def target(self):
        return self._target

    @target.setter
    def target(self, value):
        assert isinstance(value, str) or isinstance(value, Observable)
        self._target = value

    @property
    def json(self):
        return {
            Relationship.KEY_RELATIONSHIP_TYPE: self.r_type,
            Relationship.KEY_RELATIONSHIP_TARGET: self.target.id
        }

    @json.setter
    def json(self, value):
        assert isinstance(value, dict)
        if Relationship.KEY_RELATIONSHIP_TYPE in value:
            self.r_type = value[Relationship.KEY_RELATIONSHIP_TYPE]
        if Relationship.KEY_RELATIONSHIP_TARGET in value:
            self.target = value[Relationship.KEY_RELATIONSHIP_TARGET]

class Observable(TaggableObject, DetectableObject, MergableObject):
    """Represents a piece of information discovered in an analysis that can itself be analyzed."""

    KEY_ID = 'id'
    KEY_TYPE = 'type'
    KEY_VALUE = 'value'
    KEY_TIME = 'time'
    KEY_ANALYSIS = 'analysis'
    KEY_DIRECTIVES = 'directives'
    KEY_REDIRECTION = 'redirection'
    KEY_LINKS = 'links'
    KEY_LIMITED_ANALYSIS = 'limited_analysis'
    KEY_EXCLUDED_ANALYSIS = 'excluded_analysis'
    KEY_RELATIONSHIPS = 'relationships'
    KEY_GROUPING_TARGET = 'grouping_target'
    KEY_REQUEST_TRACKING = 'request_tracking'

    def __init__(self, 
            type: str = None, 
            value: str = None, 
            time: Union[datetime.datetime, str, None] = None, 
            json: Optional[dict] = None, 
            directives: Optional[list[str]] = None, 
            redirection: Optional[Observable] = None, 
            links: Optional[list[str]] = None, 
            limited_analysis: Optional[list[str]] = None, 
            excluded_analysis: Optional[list[str]] = None, 
            relationships: Optional[list[Relationship]] = None,
            *args, **kwargs):

        super().__init__(*args, **kwargs)

        self._directives = []
        self._redirection = None
        self._links = []
        self._limited_analysis = []
        self._excluded_analysis = []
        self._relationships = []
        self._grouping_target = False
        self._request_tracking = {}

        if json is not None:
            self.json = json
        else:
            self._id = str(uuid.uuid4())
            self._type = type
            self.value = value
            self._time = time
            self._analysis = {}
            self._directives = directives or [] # of str
            self._redirection = redirection or None # (str)
            self._links = links or [] # [ str ]
            self._limited_analysis = limited_analysis or [] # [ str ]
            self._excluded_analysis = excluded_analysis or [] # [ str ]
            self._relationships = relationships or [] # [ Relationship ]
            self._grouping_target = False
            self._request_tracking = {} # key = AnalysisModuleType.name, value = AnalysisRequest.id

        # reference to the RootAnalysis object
        self.root = None

    def track_analysis_request(self, ar: 'ace.system.analysis_request.AnalysisRequest'):
        """Tracks the request for analyze this Observable for the given type of analysis."""
        from ace.system.analysis_request import AnalysisRequest
        assert isinstance(ar, AnalysisRequest)

        logging.debug(f"tracking analysis request {ar} for {self}")
        self.request_tracking[ar.type.name] = ar.id

    @staticmethod
    def from_json(json_data):
        """Returns an object inheriting from Observable built from the given json."""
        from ace.system.observables import create_observable
        result = create_observable(json_data[Observable.KEY_TYPE], json_data[Observable.KEY_VALUE])
        if result:
            result.json = json_data
            return result

        return None

    def matches(self, value):
        """Returns True if the given value matches this value of this observable.  This can be overridden to provide more advanced matching such as CIDR for ipv4."""
        return self.value == value

    @property
    def json(self):
        result = TaggableObject.json.fget(self)
        result.update(DetectableObject.json.fget(self))
        result.update({
            Observable.KEY_ID: self.id,
            Observable.KEY_TYPE: self.type,
            Observable.KEY_TIME: self.time,
            # TODO these should all probably save as the internal var
            Observable.KEY_VALUE: self._value,
            Observable.KEY_ANALYSIS: self.analysis,
            Observable.KEY_DIRECTIVES: self.directives,
            Observable.KEY_REDIRECTION: self._redirection,
            Observable.KEY_LINKS: self._links,
            Observable.KEY_LIMITED_ANALYSIS: self._limited_analysis,
            Observable.KEY_EXCLUDED_ANALYSIS: self._excluded_analysis,
            Observable.KEY_RELATIONSHIPS: self._relationships,
            Observable.KEY_GROUPING_TARGET: self._grouping_target,
            Observable.KEY_REQUEST_TRACKING: self._request_tracking,
        })
        return result

    def to_dict(self):
        return self.json

    @json.setter
    def json(self, value):
        assert isinstance(value, dict)
        TaggableObject.json.fset(self, value)
        DetectableObject.json.fset(self, value)

        if Observable.KEY_ID in value:
            self.id = value[Observable.KEY_ID]
        if Observable.KEY_TYPE in value:
            self.type = value[Observable.KEY_TYPE]
        if Observable.KEY_TIME in value:
            self.time = value[Observable.KEY_TIME]
        if Observable.KEY_VALUE in value:
            self._value = value[Observable.KEY_VALUE]
        if Observable.KEY_ANALYSIS in value:
            self.analysis = value[Observable.KEY_ANALYSIS]
        if Observable.KEY_DIRECTIVES in value:
            self.directives = value[Observable.KEY_DIRECTIVES]
        if Observable.KEY_REDIRECTION in value:
            self._redirection = value[Observable.KEY_REDIRECTION]
        if Observable.KEY_LINKS in value:
            self._links = value[Observable.KEY_LINKS]
        if Observable.KEY_LIMITED_ANALYSIS in value:
            self._limited_analysis = value[Observable.KEY_LIMITED_ANALYSIS]
        if Observable.KEY_EXCLUDED_ANALYSIS in value:
            self._excluded_analysis = value[Observable.KEY_EXCLUDED_ANALYSIS]
        if Observable.KEY_RELATIONSHIPS in value:
            self._relationships = value[Observable.KEY_RELATIONSHIPS]
        if Observable.KEY_GROUPING_TARGET in value:
            self._grouping_target = value[Observable.KEY_GROUPING_TARGET]
        if Observable.KEY_REQUEST_TRACKING in value:
            self._request_tracking = value[Observable.KEY_REQUEST_TRACKING]

    def load(self) -> 'Observable':
        new_analysis = {}
        for amt, analysis in self.analysis.items():
            if isinstance(analysis, dict):
                new_analysis[amt] = Analysis.from_dict(analysis)
            else:
                new_analysis[amt] = analysis

        self.analysis = new_analysis
        return self

    @staticmethod
    def from_dict(json_dict: dict) -> 'Observable':
        return Observable.from_json(json_dict)

    @property
    def id(self) -> str:
        """A unique ID for this Observable instance."""
        return self._id

    @id.setter
    def id(self, value: str):
        assert isinstance(value, str)
        self._id = value

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

    # XXX what is this used for?
    @property
    def md5_hex(self):
        """Returns the hexidecimal MD5 hash of the value of this observable."""
        md5_hasher = hashlib.md5()
        if isinstance(self.value, str):
            md5_hasher.update(self.value.encode('utf8', errors='ignore'))
        else:
            md5_hasher.update(self.value)

        return md5_hasher.hexdigest()

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
            self._time = parse_event_time(value)
        else:
            raise ValueError("time must be a datetime.datetime object or a string in the format "
                             "%Y-%m-%d %H:%M:%S %z but you passed {}".format(type(value).__name__))

    @property
    def directives(self) -> list[str]:
        return self._directives

    @directives.setter
    def directives(self, value: list[str]):
        assert isinstance(value, list)
        self._directives = value

    @property
    def remediation_targets(self):
        """Returns a list of remediation targets for the observable, by default this is an empty list."""
        return []

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

    def remove_directive(self, directive: str):
        """Removes the given directive from this observable."""
        if directive in self.directives:
            self.directives.remove(directive)
            logging.debug(f"removed directive {directive} from {self}")

        return self

    def copy_directives_to(self, target: Observable):
        """Copies all directives applied to this Observable to another Observable."""
        assert isinstance(target, Observable)
        for directive in self.directives:
            target.add_directive(directive)

    @property
    def redirection(self) -> Union[Observable, None]:
        if not self._redirection:
            return None

        return self.root.observable_store[self._redirection]

    @redirection.setter
    def redirection(self, value: Observable):
        assert isinstance(value, Observable)
        self._redirection = value.id

    @property
    def links(self):
        if not self._links:
            return []

        return [self.root.observable_store[_id] for _id in self._links]

    @links.setter
    def links(self, value):
        assert isinstance(value, list)
        for v in value:
            assert isinstance(v, Observable)

        self._links = [x.id for x in value]

    def add_link(self, target):
        """Links this Observable object to another Observable object.  Any tags
           applied to this Observable are also applied to the target Observable."""

        assert isinstance(target, Observable)

        # two observables cannot link to each other
        # that would cause a recursive loop in add_tag override
        if self in target.links:
            logging.warning("{} already links to {}".format(target, self))
            return
        
        if target.id not in self._links:
            self._links.append(target.id)

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

    def is_excluded(self, amt: Union[AnalysisModuleType, str]) -> bool:
        """Returns True if this Observable has been excluded from analysis by this AnalysisModuleType."""
        assert isinstance(amt, str) or isinstance(amt, AnalysisModuleType)
        if isinstance(amt, AnalysisModuleType):
            amt = amt.name

        return amt in self.excluded_analysis

    # XXX this needs to come out
    def remove_analysis_exclusion(self, amt: Union[AnalysisModuleType, str]):
        """Removes AnalysisModule exclusion added to this observable."""
        assert isinstance(amt, str) or isinstance(amt, AnalysisModuleType)
        if isinstance(amt, AnalysisModuleType):
            amt = amt.name

        self.excluded_analysis.remove(amt)

    @property
    def relationships(self):
        return self._relationships

    @relationships.setter
    def relationships(self, value):
        self._relationships = value

    def has_relationship(self, _type):
        for r in self.relationships:
            if r.r_type == _type:
                return True

        return False

    def _load_relationships(self):
        temp = []
        for value in self.relationships:
            if isinstance(value, dict):
                r = Relationship()
                r.json = value

                try:
                    # find the observable this points to and reference that
                    r.target = self.root._observable_store[r.target]
                except KeyError:
                    logging.error("missing observable uuid {} in {}".format(r.target, self))
                    continue

                value = r

            temp.append(value)

        self._relationships = temp

    def add_relationship(self, r_type, target):
        """Adds a new Relationship to this Observable.
           Existing relationship is returned, other new Relationship object is added and returned."""
        assert r_type in VALID_RELATIONSHIP_TYPES
        assert isinstance(target, Observable)

        for r in self.relationships:
            if r.r_type == r_type and r.target == target:
                return r

        r = Relationship(r_type, target)
        self.relationships.append(r)
        return r

    def get_relationships_by_type(self, r_type):
        """Returns the list of Relationship objects by type."""
        return [r for r in self.relationships if r.r_type == r_type]

    def get_relationship_by_type(self, r_type):
        """Returns the first Relationship found of a given type, or None if none exist."""
        result = self.get_relationships_by_type(r_type)
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
        """Returns a dict that maps the AnalysisModuleType.name to the AnalysisRequest.id."""
        assert isinstance(value, dict)
        self._request_tracking = value

    def get_analysis_request_id(self, amt: Union[AnalysisModuleType, str]) -> Union[str, None]:
        """Returns the AnalysisRequest.id for the given analysis module type, or None if nothing is tracked yet."""
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

        # set the document root for this analysis
        analysis.root = self.root
        # set the source of the Analysis
        analysis.observable = self

        # does this analysis already exist?
        if analysis.type.name in self.analysis and not (self.analysis[analysis.type.name] is analysis):
            logging.error("replacing analysis type {} with {} for {} (are you returning the correct type from generated_analysis_type()?)".format(
                self.analysis[analysis.type.name], analysis, self))

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

    def _load_analysis(self):
        assert isinstance(self.analysis, dict)

        from ace.system.analysis_module import get_analysis_module_type

        # see the module_path property of the Analysis object
        for amt_type_name in self.analysis.keys():
            # have we already translated this?
            if isinstance(self.analysis[amt_type_name], Analysis):
                continue

            # this should be a json dict
            assert isinstance(self.analysis[amt_type_name], dict)

            analysis = Analysis(
                root = self.root,
                type = get_analysis_module_type(amt_type_name),
                observable = self)

            analysis.json = self.analysis[amt_type_name]
            self.analysis[amt_type_name] = analysis # replace the JSON dict with the actual object

    # XXX refactor
    def clear_analysis(self):
        """Deletes all analysis records for this observable."""
        self.analysis = {}

    def search_tree(self, tags=()):
        """Searches this object and every object in it's analysis tree for the given items.  Returns the list of items that matched."""

        if not isinstance(tags, tuple):
            tags = (tags,)
        
        result = []
        def _search(target):
            for tag in tags:
                if target.has_tag(tag):
                    if target not in result:
                        result.append(target)

        recurse_tree(self, _search)
        return result

    def apply_merge(self, target: 'Observable') -> 'Observable':
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

        for rel in target.relationships:
            # get a reference to the local copy of the target observable
            local_observable = self.root.get_observable(rel.target)
            if not local_observable:
                # if we can't get it then add it
                local_observable = self.root.add_observable(rel.target)
            
            self.add_relationship(rel.r_type, local_observable)

        if target.grouping_target:
            self.grouping_target = target.grouping_target

        for tag in target.tags:
            self.add_tag(tag)

        for amt, analysis in target.analysis.items():
            existing_analysis = self.get_analysis(amt)
            if not existing_analysis:
                # add any missing analysis
                self.add_analysis(analysis)
            else:
                # merge existing analysi
                existing_analysis.apply_merge(analysis)

        return self

    def apply_diff_merge(self, before: 'Observable', after: 'Observable') -> 'Observable':
        """Merge all the mergable properties of the target Observable into this observable."""
        assert isinstance(before, Observable)
        assert isinstance(after, Observable)
        assert before.type == after.type == self.type
        assert before.value == after.value == self.value

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

        for rel in after.relationships:
            if rel in before.relationships:
                continue

            # get a reference to the local copy of the target observable
            local_observable = self.root.get_observable(rel.target)
            if not local_observable:
                # if we can't get it then add it
                local_observable = self.root.add_observable(rel.target)
            
            self.add_relationship(rel.r_type, local_observable)

        if before.grouping_target != after.grouping_target:
            self.grouping_target = after.grouping_target

        for amt, analysis in after.analysis.items():
            if before.get_analysis(amt):
                continue

            # add any missing analysis
            self.add_analysis(analysis)

        return self

    def create_analysis_request(self, amt: AnalysisModuleType) -> 'ace.system.analysis_request.AnalysisRequest':
        """Creates and returns a new ace.system.analysis_request.AnalysisRequest object from this Observable."""
        from ace.system.analysis_request import AnalysisRequest
        return AnalysisRequest(root=self.root, observable=self, type=amt)

    def __str__(self):
        if self.time is not None:
            return u'{}({}@{})'.format(self.type, self.value, self.time)
        else:
            return u'{}({})'.format(self.type, self.value)

    # XXX there is also a match function for this?
    def _compare_value(self, other_value):
        """Default implementation to compare the value of this observable to the value of another observable.
           By default does == comparison, can be overridden."""
        return self.value == other_value

    def __eq__(self, other):
        if not isinstance(other, Observable):
            return False

        # exactly the same?
        if other.id == self.id:
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

class CaselessObservable(Observable):
    """An observable that doesn't care about the case of the value."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    # see https://stackoverflow.com/a/29247821
    def normalize_caseless(self, value):
        if value is None:
            return None

        return unicodedata.normalize("NFKD", value.casefold())

    def _compare_value(self, other):
        return self.normalize_caseless(self.value) == self.normalize_caseless(other)

class RootAnalysis(Analysis, MergableObject):
    """Root analysis object."""

    def __init__(self, 
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
                 version=0,
                 *args, **kwargs):

        import uuid as uuidlib

        super().__init__(*args, **kwargs)

        # we are the root
        self.root = self

        self._original_analysis_mode = None
        self._analysis_mode = None
        if analysis_mode:
            self.analysis_mode = analysis_mode

        self._uuid = str(uuidlib.uuid4()) # default is new uuid
        if uuid:
            self.uuid = uuid

        self._version = 0
        if version is not None:
            self.version = version

        self._tool = None
        if tool:
            self.tool = tool

        self._tool_instance = None
        if tool_instance:
            self.tool_instance = tool_instance

        self._alert_type = None
        if alert_type:
            self.alert_type = alert_type

        self._queue = QUEUE_DEFAULT
        if queue:
            self.queue = queue

        self._description = None
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

        self._state = {}
        if state:
            self.state = state

        # all of the Observables discovered during analysis go into the observable_store
        # these objects are what are serialized to and from JSON
        self._observable_store = {} # key = uuid, value = Observable object

        # set to True after load() is called
        self.is_loaded = False
        
    #
    # the json property is used for internal storage
    #
    
    # json keys
    KEY_ANALYSIS_MODE = 'analysis_mode'
    KEY_ID = 'id'
    KEY_VERSION = 'version'
    KEY_UUID = 'uuid'
    KEY_TOOL = 'tool'
    KEY_TOOL_INSTANCE = 'tool_instance'
    KEY_TYPE = 'type'
    KEY_DESCRIPTION = 'description'
    KEY_EVENT_TIME = 'event_time'
    KEY_DETAILS = 'details'
    KEY_OBSERVABLE_STORE = 'observable_store'
    KEY_NAME = 'name'
    KEY_NETWORK = 'network'
    KEY_QUEUE = 'queue'
    KEY_INSTRUCTIONS = 'instructions'

    def to_dict(self) -> dict:
        return self.json

    @staticmethod
    def from_dict(root_dict: dict):
        result = RootAnalysis()
        result.json = root_dict
        return result

    @property
    def json(self):
        result = Analysis.json.fget(self)
        result.update({
            RootAnalysis.KEY_ANALYSIS_MODE: self.analysis_mode,
            RootAnalysis.KEY_UUID: self.uuid,
            RootAnalysis.KEY_VERSION: self.version,
            RootAnalysis.KEY_TOOL: self.tool,
            RootAnalysis.KEY_TOOL_INSTANCE: self.tool_instance,
            RootAnalysis.KEY_TYPE: self.alert_type,
            RootAnalysis.KEY_DESCRIPTION: self.description,
            RootAnalysis.KEY_EVENT_TIME: self.event_time,
            #RootAnalysis.KEY_DETAILS: self.details, <-- this is saved externally
            RootAnalysis.KEY_OBSERVABLE_STORE: self.observable_store,
            RootAnalysis.KEY_NAME: self.name,
            RootAnalysis.KEY_QUEUE: self.queue,
            RootAnalysis.KEY_INSTRUCTIONS: self.instructions,
        })
        return result

    @json.setter
    def json(self, value):
        assert isinstance(value, dict)

        # this is important to do first before we load Observable references
        if RootAnalysis.KEY_OBSERVABLE_STORE in value:
            self.observable_store = value[RootAnalysis.KEY_OBSERVABLE_STORE]

        Analysis.json.fset(self, value)

        # load this alert from the given json data
        if RootAnalysis.KEY_ANALYSIS_MODE in value:
            self.analysis_mode = value[RootAnalysis.KEY_ANALYSIS_MODE]
        if RootAnalysis.KEY_UUID in value:
            self.uuid = value[RootAnalysis.KEY_UUID]
        if RootAnalysis.KEY_VERSION in value:
            self.version = value[RootAnalysis.KEY_VERSION]
        if RootAnalysis.KEY_TOOL in value:
            self.tool = value[RootAnalysis.KEY_TOOL]
        if RootAnalysis.KEY_TOOL_INSTANCE in value:
            self.tool_instance = value[RootAnalysis.KEY_TOOL_INSTANCE]
        if RootAnalysis.KEY_TYPE in value:
            self.alert_type = value[RootAnalysis.KEY_TYPE]
        if RootAnalysis.KEY_DESCRIPTION in value:
            self.description = value[RootAnalysis.KEY_DESCRIPTION]
        if RootAnalysis.KEY_EVENT_TIME in value:
            self.event_time = value[RootAnalysis.KEY_EVENT_TIME]
        if RootAnalysis.KEY_NAME in value:
            self.name = value[RootAnalysis.KEY_NAME]
        if RootAnalysis.KEY_QUEUE in value:
            self.queue = value[RootAnalysis.KEY_QUEUE]
        if RootAnalysis.KEY_INSTRUCTIONS in value:
            self.instructions = value[RootAnalysis.KEY_INSTRUCTIONS]

    @property
    def analysis_mode(self):
        return self._analysis_mode

    @property
    def original_analysis_mode(self):
        return self._original_analysis_mode

    @analysis_mode.setter
    def analysis_mode(self, value):
        assert value is None or ( isinstance(value, str) and value )
        self._analysis_mode = value
        if self._original_analysis_mode is None:
            self._original_analysis_mode = value

    def override_analysis_mode(self, value):
        """Change the analysis mode and disregard current values.
           This has the effect of setting both the analysis mode and original analysis mode."""
        assert value is None or ( isinstance(value, str) and value )
        self._analysis_mode = value
        self._original_analysis_mode = value

    @property
    def uuid(self):
        return self._uuid

    @uuid.setter
    def uuid(self, value):
        assert isinstance(value, str)
        self._uuid = value

    @property
    def version(self) -> int:
        """Returns the current version of this RootAnalysis object.
        The version starts at 0 and increments every time the object is modified and saved."""
        return self._version

    @version.setter
    def version(self, value: int):
        assert isinstance(value, int) and value >= 0
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
            self._event_time = parse_event_time(value)
        else:
            raise ValueError("event_time must be a datetime.datetime object or a string in the format "
                             "%Y-%m-%d %H:%M:%S %z but you passed {}".format(type(value).__name__))

    @property
    def event_time_datetime(self):
        """This returns the same thing as event_time. It remains for backwards compatibility."""
        return self._event_time

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

    def initialize_storage(self, path: Optional[str]=None) -> bool:
        """Initializes and creates a local storage directory if one does not
        already exist.  If the path is specified it is used as the storage
        directory, otherwise a temporary directory is created in ace.TEMP_DIR.
        """
        if self.storage_dir is None:
            if path:
                self.storage_dir = path
            else:
                self.storage_dir = tempfile.mkdtemp(dir=ace.TEMP_DIR)

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

    # XXX one of these should go away
    def record_observable(self, observable):
        """Records the given observable into the observable_store if it does not already exist.  
           Returns the new one if recorded or the existing one if not."""
        assert isinstance(observable, Observable)

        # XXX gross this is probably pretty inefficient
        for o in self.observable_store.values():
            if o == observable:
                logging.debug("returning existing observable {} ({}) [{}] <{}> for {} ({}) [{}] <{}>".format(o, id(o), o.id, o.type, observable, id(observable), observable.id, observable.type))
                return o

        observable.root = self
        self.observable_store[observable.id] = observable
        logging.debug("recorded observable {} with id {}".format(observable, observable.id))
        return observable

    def record_observable_by_spec(self, o_type, o_value, o_time=None):
        """Records the given observable into the observable_store if it does not already exist.  
           Returns the new one if recorded or the existing one if not."""
        from ace.system.observables import create_observable

        assert isinstance(o_type, str)
        assert isinstance(self.observable_store, dict)
        assert o_time is None or isinstance(o_time, str) or isinstance(o_time, datetime.datetime)

        # create a temporary object to make use of any defined custom __eq__ ops
        observable = create_observable(o_type, o_value, o_time=o_time)
        if observable is None:
            return None

        return self.record_observable(observable)

    def save(self):
        from ace.system.analysis_tracking import track_root_analysis
        track_root_analysis(self)

        for analysis in self.all_analysis:
            if analysis is not self:
                analysis.save()

        # save our own details
        return Analysis.save(self)

    # XXX refactor
    def flush(self):
        """Calls Analysis.flush on all Analysis objects in this RootAnalysis."""
        #logging.debug("called RootAnalysis.flush() on {}".format(self))
        #Analysis.flush(self) # <-- we don't want to flush out the RootAnalysis details

        # make sure the containing directory exists
        if not os.path.exists(os.path.join(ace.SAQ_RELATIVE_DIR, self.storage_dir)):
            os.makedirs(os.path.join(ace.SAQ_RELATIVE_DIR, self.storage_dir))

        # analysis details go into a hidden directory
        if not os.path.exists(os.path.join(ace.SAQ_RELATIVE_DIR, self.storage_dir, '.ace')):
            os.makedirs(os.path.join(ace.SAQ_RELATIVE_DIR, self.storage_dir, '.ace'))

        for analysis in self.all_analysis:
            if analysis is not self:
                analysis.flush()

        freed_items = gc.collect()
        #logging.debug("{} items freed by gc".format(freed_items))

    def load(self):
        """Utility function to replace specific dict() in json with runtime object references."""
        # in other words, load the JSON
        self._load_observable_store()

        # load the Analysis objects in the Observables
        for observable in self.observable_store.values():
            observable._load_analysis()

        # load the Observable references in the Analysis objects
        for analysis in self.all_analysis:
            analysis._load_observable_references()

        # load DetectionPoints
        for analysis in self.all_analysis:
            analysis.detections = [DetectionPoint.from_json(dp) for dp in analysis.detections]

        for observable in self.all_observables:
            observable.detections = [DetectionPoint.from_json(dp) for dp in observable.detections]

        # load Relationships
        for observable in self.all_observables:
            observable._load_relationships()

        return self
        
    def _load_observable_store(self):
        from ace.system.observables import create_observable
        invalid_uuids = [] # list of uuids that don't load for whatever reason
        for uuid in self.observable_store.keys():
            # get the JSON dict from the observable store for this uuid
            value = self.observable_store[uuid]
            # create the observable from the type and value
            o = create_observable(value['type'], value['value'])
            # basically this is backwards compatibility with old alerts that have invalid values for observables
            if o:
                o.root = self
                o.json = value # this sets everything else

                self.observable_store[uuid] = o
            else:
                logging.warning("invalid observable type {} value {}".format(value['type'], value['value']))
                invalid_uuids.append(uuid)

        for uuid in invalid_uuids:
            del self.observable_store[uuid]

    # XXX reset
    def reset(self):
        """Removes analysis, dispositions and any observables that did not originally come with the alert."""
        from ace.database import acquire_lock, release_lock, LockedException

        lock_uuid = None
        try:
            lock_uuid = acquire_lock(self.uuid)
            if not lock_uuid:
                raise LockedException(self)

            return self._reset()

        finally:
            if lock_uuid:
                release_lock(self.uuid, lock_uuid)

    # XXX refactor
    def _reset(self):
        from subprocess import Popen

        logging.info("resetting {}".format(self))

        # NOTE that we do not clear the details that came with Alert
        # clear external details storage for all analysis (except self)
        for _analysis in self.all_analysis:
            if _analysis is self:
                continue

            _analysis.reset()

        # remove analysis objects from all observables
        for o in self.observables:
            o.clear_analysis()

        # remove observables from the observable_store that didn't come with the original alert
        #import pdb; pdb.set_trace()
        original_uuids = set([o.id for o in self.observables])
        remove_list = []
        for uuid in self.observable_store.keys():
            if uuid not in original_uuids:
                remove_list.append(uuid)

        for uuid in remove_list:
            # if the observable is a F_FILE then try to also delete the file
            if self.observable_store[uuid].type == F_FILE:
                target_path = abs_path(self.observable_store[uuid].value)
                if os.path.exists(target_path):
                    logging.debug("deleting observable file {}".format(target_path))

                    try:
                        os.remove(target_path)
                    except Exception as e:
                        logging.error("unable to remove {}: {}".format(target_path, str(e)))

            del self.observable_store[uuid]

        # remove tags from observables
        # NOTE there's currently no way to know which tags originally came with the alert
        for o in self.observables:
            o.clear_tags()

        # clear the state
        # this also clears any pre/post analysis module tracking
        self.state = {}

        # remove any empty directories left behind
        logging.debug("removing empty directories inside {}".format(self.storage_dir))
        p = Popen(['find', abs_path(self.storage_dir), '-type', 'd', '-empty', '-delete'])
        p.wait()

    # XXX not quite sure we really need this but refactor if we do
    def archive(self):
        """Removes the details of analysis and external files.  Keeps observables and tags."""
        from subprocess import Popen

        logging.info("archiving {}".format(self))

        # NOTE that we do not clear the details that came with Alert
        # clear external details storage for all analysis (except self)
        for _analysis in self.all_analysis:
            if _analysis is self:
                continue

            _analysis.reset()

        retained_files = set()
        for o in self.all_observables:
            # skip the ones that came with the alert
            if o in self.observables:
                logging.debug("{} came with the alert (skipping)".format(o))
                if o.type == F_FILE:
                    retained_files.add(os.path.join(ace.SAQ_RELATIVE_DIR, self.storage_dir, o.value))

                continue

            if o.type == F_FILE:
                target_path = os.path.join(ace.SAQ_RELATIVE_DIR, self.storage_dir, o.value)
                if os.path.exists(target_path):
                    logging.debug("deleting observable file {}".format(target_path))

                    try:
                        os.remove(target_path)
                    except Exception as e:
                        logging.error("unable to remove {}: {}".format(target_path, str(e)))

        for dir_path, dir_names, file_names in os.walk(os.path.join(ace.SAQ_RELATIVE_DIR, self.storage_dir)):
            # ignore anything in the root of the storage directory
            if dir_path == os.path.join(ace.SAQ_RELATIVE_DIR, self.storage_dir):
                logging.debug("skipping core directory {}".format(dir_path))
                continue

            # and ignore anything in the .ace subdirectory
            if dir_path == os.path.join(ace.SAQ_RELATIVE_DIR, self.storage_dir, '.ace'):
                logging.debug("skipping core directory {}".format(dir_path))
                continue

            for file_name in file_names:
                file_path = os.path.join(dir_path, file_name)
                # and ignore any F_FILE we wanted to keep
                if file_path in retained_files:
                    logging.debug("skipping retained file {}".format(file_path))
                    continue

                try:
                    logging.debug("deleting {}".format(file_path))
                    os.remove(file_path)
                except Exception as e:
                    logging.error("unable to remove {}: {}".format(file_path, e))
                    report_exception()

        # remove any empty directories left behind
        logging.debug("removing empty directories inside {}".format(self.storage_dir))
        p = Popen(['find', os.path.join(ace.SAQ_HOME, self.storage_dir), '-type', 'd', '-empty', '-delete'])
        p.wait()

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

    def set_analysis(self, observable: Observable, analysis: Analysis):
        assert isinstance(observable, Observable)
        assert isinstance(analysis, Analysis)
        assert isinstance(analysis.type, AnalysisModuleType)

        observable = self.get_observable(observable)
        if observable is None:
            raise UnknownObservableError(observable)

        return observable.add_analysis(analysis)

    @property
    def all_iocs(self) -> list:
        iocs = IndicatorList()

        for analysis in self.all_analysis:
            for ioc in analysis.iocs:
                iocs.append(ioc)

        return iocs

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

    def iterate_all_references(self, target):
        """Iterators through all objects that refer to target."""
        if isinstance(target, Observable):
            for analysis in self.all_analysis:
                if target in analysis.observables:
                    yield analysis
        elif isinstance(target, Analysis):
            for observable in self.all_observables:
                if target in observable.all_analysis:
                    yield observable
        else:
            raise ValueError("invalid type {} passed to iterate_all_references".format(type(target)))

    def get_observable(self, uuid_or_observable:Union[str, Observable]):
        """Returns the Observable object for the given uuid or None if the Observable does not exist."""
        assert isinstance(uuid_or_observable, str) or isinstance(uuid_or_observable, Observable)

        # if we passed the id of an Observable then we return that specific Observable or None if it does not exist
        if isinstance(uuid_or_observable, str):
            return self.observable_store.get(uuid_or_observable, None)

        observable = uuid_or_observable

        try:
            # if we passed an existing Observable (same id) then we return the reference inside the RootAnalysis
            # with the matching id
            return self.observable_store[observable.id]
        except KeyError:
            # otherwise we try to match based on the type, value and time
            return self.find_observable(
                lambda o: o.type == observable.type and o.value == observable.value and o.time == observable.time)

    def get_observable_by_spec(self, o_type, o_value, o_time=None):
        """Returns the Observable object by type and value, and optionally time, or None if it cannot be found."""
        target = Observable(o_type, o_value, o_time)
        for o in self.all_observables:
            if o == target:
                return o

        return None

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
        observable = self.get_observable_by_spec(observable.type, observable.value)
        if observable is None:
            raise UnknownObservableError(observable)

        return observable.analysis_completed(amt)

    def analysis_tracked(self, observable: Observable, amt: AnalysisModuleType) -> bool:
        """Returns True if the analysis for the given Observable and type is already requested (tracked.)"""
        assert isinstance(observable, Observable)
        assert isinstance(amt, AnalysisModuleType)

        observable = self.get_observable_by_spec(observable.type, observable.value)
        if observable is None:
            raise UnknownObservableError(observable)

        return observable.get_analysis_request_id(amt) is not None

    def apply_merge(self, target: 'RootAnalysis') -> 'RootAnalysis':
        """Merge all the mergable properties of the target RootAnalysis into this root."""
        assert isinstance(target, RootAnalysis)
        Analysis.apply_merge(self, target)

        # you cannot merge two different root analysis objects together
        if self.uuid != target.uuid:
            logging.error(f"attempting to merge a different RootAnalysis ({target}) into {self}")
            return None

        # merge any properties that can be modified after a RootAnalysis is created
        self.analysis_mode = target.analysis_mode
        self.queue = target.queue
        self.description = target.description
        return self

    def apply_diff_merge(self, before: 'RootAnalysis', after: 'RootAnalysis') -> 'RootAnalysis':
        assert isinstance(before, RootAnalysis)
        assert isinstance(after, RootAnalysis)

        if before.uuid != after.uuid:
            logging.error(f"attempting to apply diff merge against two difference roots {before} and {after}")
            return None

        TaggableObject.apply_diff_merge(self, before, after)
        DetectableObject.apply_diff_merge(self, before, after)

        if before.analysis_mode != after.analysis_mode:
            self.analysis_mode = after.analysis_mode

        if before.queue != after.queue:
            self.queue = after.queue

        if before.description != after.description:
            self.description = after.description

        return self

def recurse_down(target, callback):
    """Calls callback starting at target back to the RootAnalysis."""
    assert isinstance(target, Analysis) or isinstance(target, Observable)
    assert isinstance(target.root, RootAnalysis)

    visited = [] # keep track of what we've looked at
    root = target.root 

    def _recurse(target, callback):
        nonlocal visited, root
        # make sure we haven't already looked at this one
        if target in visited:
            return

        # are we at the end?
        if target is root:
            return

        visited.append(target)

        if isinstance(target, Observable):
            # find all Analysis objects that reference this Observable
            for analysis in root.all_analysis:
                for observable in analysis.observables:
                    # not sure the == part is needed but just in case I screw up later...
                    if target is observable or target == observable:
                        callback(analysis)
                        _recurse(analysis, callback)

        elif isinstance(target, Analysis):
            # find all Observable objects that reference this Analysis
            for observable in root.all_observables:
                for analysis in observable.all_analysis:
                    if analysis is target:
                        callback(observable)
                        _recurse(observable, callback)

    _recurse(target, callback)

def search_down(target, callback):
    """Searches from target down to RootAnalysis looking for callback(obj) to return True."""
    result = None

    def _callback(target):
        nonlocal result
        if result:
            return

        if callback(target):
            result = target

    recurse_down(target, _callback)
    return result

def recurse_tree(target, callback):
    """A utility function to run the given callback on every Observable and Analysis rooted at the given Observable or Analysis object."""
    assert isinstance(target, Analysis) or isinstance(target, Observable)

    def _recurse(target, visited, callback):
        callback(target)
        visited.append(target)

        if isinstance(target, Analysis):
            for observable in target.observables:
                if observable not in visited:
                    _recurse(observable, visited, callback)
        elif isinstance(target, Observable):
            for analysis in target.all_analysis:
                if analysis and analysis not in visited:
                    _recurse(analysis, visited, callback)

    _recurse(target, [], callback)
