# vim: sw=4:ts=4:et:cc=120

import datetime
import json
import uuid

from typing import Optional, Any, Union

from ace.time import utc_now

from pydantic import BaseModel, Field
from pydantic.json import pydantic_encoder


class DetectionPointModel(BaseModel):
    """Represents a detection made during analysis."""

    description: str = Field(..., description="brief one line description of what was detected")
    details: Optional[str] = Field(description="optional detailed description of the detection")


class DetectableObjectModel(BaseModel):
    """Base class for objects that can have Detection Points."""

    detections: Optional[list[DetectionPointModel]] = Field(
        description="the list of detection points", default_factory=list
    )


class TaggableObjectModel(BaseModel):
    tags: Optional[list[str]] = Field(description="the list of tags added to this object", default_factory=list)


class AnalysisModuleTypeModel(BaseModel):
    name: str = Field(
        ..., description="the name of the analysis module which must be unique to another analysis modules"
    )
    description: str = Field(..., description="human readable description of what the analysis module does")
    observable_types: list[str] = Field(
        default_factory=list,
        description="""List of observable types this analysis module will analyze. 
    An empty list means all observable types are supported.""",
    )
    directives: list[str] = Field(
        default_factory=list,
        description="""List of required directives for this analysis module.
        An observable must have ALL of these directives added for this analysis module to accept it.
        An empty list means this analysis module has no required directives.""",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="""The list of analysis modules this module is dependant on.
    ACE waits until all dependencies are met before submitting the analysis request to the module.
    Analysis requests will contain the results of the dependent analysis.
    An empty list means this analysis module has no dependencies.""",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="""The list of all required tags for this analysis module.
    An analysis request will not created for this analysis module unless the target observable has all the tags listed.
    An empty list means this module has no required tags.""",
    )
    modes: list[str] = Field(
        default_factory=list,
        description="""The list of valid analysis modes for this module.
    The analysis_mode property of the RootAnalysis must be set to one of these values.
    An empty list means that this module runs in all analysis modes.""",
    )
    conditions: list[str] = Field(
        default_factory=list,
        description="""TODO""",
    )
    version: str = Field(
        "1.0.0",
        description="""Free form version of the module.
    This value should be updated when the analysis module is updated.""",
    )
    timeout: int = Field(
        30,
        description="""The amount of time (in seconds) the module has to
        analyze the observable until it is considered to be timed out.""",
    )
    cache_ttl: Optional[int] = Field(
        description="""The amount of time (in seconds) that analysis results generated by this module are cached. 
        Setting this value to None disables caching for this module."""
    )
    extended_version: list[str] = Field(
        default_factory=list,
        description="""A list of arbitrary values to be included when generating a cache key.
        The cache key are the values that are used to look up results in the result cache. By default ACE uses the

        - type
        - value
        - time (if available)
        - name
        - version

        All elements of this list are appended. For example, if the analysis
        module uses signatures, the hash of the signatures could be used here
        which would automatically invalidate cache results when it changed.""",
    )
    types: list[str] = Field(default_factory=list, description="""Optional list of module catagorization types.""")
    manual: Optional[bool] = Field(
        description="""If set to True then this analysis module only execute when requested."""
    )


class AnalysisModel(DetectableObjectModel, TaggableObjectModel, BaseModel):
    """The results of an analysis performed by an analysis module on an observable."""

    uuid: Optional[str] = Field(
        default_factory=lambda: str(uuid.uuid4()), description="Unique identifier for this analysis." ""
    )
    type: Optional[AnalysisModuleTypeModel] = Field(description="""The analysis module that generated this result.""")
    observable_id: Optional[str] = Field(description="""The observable this analysis is for.""")
    observable_ids: Optional[list[str]] = Field(
        default_factory=list, description="""The list of observables discovered during this analysis."""
    )
    summary: Optional[str] = Field(description="""A brief human readable description of the results of the analysis.""")
    details: Optional[Any] = Field(
        description="""The free-form result of the analysis (must be a serializable into JSON.)"""
    )
    error_message: Optional[str] = Field(description="""The error message for when analysis has failed.""")
    stack_trace: Optional[str] = Field(description="""Optional stack trace for error messages.""")


class ObservableModel(DetectableObjectModel, TaggableObjectModel, BaseModel):
    """Something that was observed during analysis."""

    uuid: Optional[str] = Field(
        default_factory=lambda: str(uuid.uuid4()), description="Unique identifier for this observable." ""
    )

    type: str = Field(
        ...,
        description="""The type of the observable. This can
            be a string of any value, but the value may have meaning to another
            analysis modules.""",
    )

    value: str = Field(
        ...,
        description="""Free form value of the observable.
            The precise meaning of the value depends on the type. Complex
            values should be base64 encoded.""",
    )

    time: Optional[datetime.datetime] = Field(
        description="""Optional time at which the value was observed.
        Observables without time are assumed to have occured when the root
        event occured."""
    )

    analysis: Optional[dict[str, AnalysisModel]] = Field(
        default_factory=dict,
        description="""The record of all analysis performed on this
            observable. The keys are the names of the analysis module types.
            The values are the analyis objects for the module types.""",
    )

    directives: Optional[list[str]] = Field(
        default_factory=list, description="""The list of directives added to this observable."""
    )

    redirection: Optional[str] = Field(description="""Optional observable target for redirection.""")
    links: Optional[list[str]] = Field(
        default_factory=list,
        description="""The list of observables linked to this observable.
            Observables that are linked receive the same tags.""",
    )
    limited_analysis: Optional[list[str]] = Field(
        default_factory=list,
        description="""The list of analysis modules this observable is
            limited to. The modules in this list are the only modules that will
            analyze this observable. An empty list means there are no
            limitation.""",
    )
    excluded_analysis: Optional[list[str]] = Field(
        default_factory=list,
        description="""The list of analysis modules that are excluded by
            this observable. Modules in this list are not executed against this
            observable. An empty list means nothing is excluded.""",
    )
    requested_analysis: Optional[list[str]] = Field(
        default_factory=list,
        description="""The list of analysis modules that have been requested
        for this observable.  This is the only means of executing manual
        analysis modules. An empty list means nothing is specifically
        requested.""",
    )
    relationships: Optional[dict[str, list[str]]] = Field(
        default_factory=dict,
        description="""A mapping of relationships between this observable
            and other observables. The key is the name of the relationship. The
            value for each key is a list of one or more observables related in
            this way.""",
    )
    grouping_target: Optional[bool] = Field(
        description="""An optional boolean value that indicates this
            observable should be used as the "grouping target" for all
            observables of it's type."""
    )
    request_tracking: Optional[dict[str, str]] = Field(
        default_factory=dict,
        description="""The mapping of analysis requests for this observable.
        The key is the analysis module type, the value is the analysis
        request.""",
    )


class RootAnalysisModel(AnalysisModel, BaseModel):
    tool: Optional[str] = Field(
        description="""The name of the tool that
            generated the alert (ex: splunk)."""
    )
    tool_instance: Optional[str] = Field(
        description="""The instance of the
            tool that generated the alert (ex: the hostname of the sensor)."""
    )
    alert_type: Optional[str] = Field(description="""The type of the alert (ex: splunk - ipv4 search).""")
    description: Optional[str] = Field(
        """A brief one line description of the
            alert (ex: high_pdf_xor_kernel32 match in email attachment)."""
    )
    event_time: Optional[datetime.datetime] = Field(
        default_factory=utc_now,
        description="""Returns a datetime object representing the time this
            event was created or occurred.""",
    )
    name: Optional[str] = Field(
        description="""An optional property that defines a name for an alert.
        Used to track and document analyst response instructions."""
    )
    state: Optional[dict] = Field(
        default_factory=dict,
        description="""A free form dict that can store any value. Used by
        AnalysisModules to maintain state.""",
    )
    analysis_mode: Optional[str] = Field(
        description="""The current analysis mode. The mode determines what
            analysis modules are executed against the observables in this
            root."""
    )
    queue: Optional[str] = Field(
        description="""The optional name of the queue this alert should be put
        into."""
    )
    instructions: Optional[str] = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="""An optional human readable list of instructions that an
        analyst should perform when manually reviewing this alert.""",
    )
    version: Optional[str] = Field(
        description="""An optional version string that automatically changes
        every time the root is modified. The version must match when updating."""
    )
    expires: Optional[bool] = Field(
        False,
        description="""An optional boolean value if determines if this root
        will expire. If this is set to True this root analysis will
        automatically be deleted if all analysis has been completed and no
        detection points were added.""",
    )
    analysis_cancelled: Optional[bool] = Field(
        False, description="""Set this value to True to cancel any outstanding analysis requests for this root."""
    )
    analysis_cancelled_reason: Optional[str] = Field(
        description="""Optional human readable description of why analysis was canceled for this root."""
    )
    observable_store: Optional[dict[str, ObservableModel]] = Field(
        default_factory=dict,
        description="""The mapping that contains all observables for this
        entire root. The key is the uuid of the observable, the value is the
        observable. All analysis references these objects by their keys.""",
    )


class AnalysisRequestModel(BaseModel):
    id: Optional[str] = Field(
        default_factory=lambda: str(uuid.uuid4()), description="""The unique id for this request."""
    )
    root: Optional[Union[str, RootAnalysisModel]] = Field(
        description="""The root this request is for. If this is a string
            then it is a reference to an existing analysis. Otherwise it is a
            full root object."""
    )
    observable: Optional[ObservableModel] = Field(description="""The observable this request is for.""")
    type: Optional[AnalysisModuleTypeModel] = Field(description="""The analysis module type this request is for.""")
    cache_hit: Optional[bool] = Field(
        False, description="""If this is True then this request is the result of a cache hit."""
    )
    status: Optional[str] = Field(description="""The current status of this analysis request.""")
    owner: Optional[str] = Field(description="""The current owner of this analysis request.""")
    original_root: Optional[RootAnalysisModel] = Field(
        description="""The root as it existed before analysis started."""
    )
    modified_root: Optional[RootAnalysisModel] = Field(
        description="""The root as it existed after analyisis completed."""
    )


class ContentMetadata(BaseModel):
    name: str = Field(description="""Name of the content which can be anything such as the name of the file.""")
    sha256: Optional[str] = Field(description="""SHA2 (lowercase hex) of the content.""")
    size: Optional[int] = Field(description="""Size of the content in bytes.""")
    insert_date: Optional[datetime.datetime] = Field(
        default_factory=utc_now,
        description="""When the content was created. Defaults to now.""",
    )
    roots: Optional[list[str]] = Field(
        default_factory=list,
        description="""List of RootAnalysis UUIDs that reference this content.""",
    )
    location: Optional[str] = Field(description="""Free-form location of the content. Can be None if not used.""")
    expiration_date: Optional[datetime.datetime] = Field(
        description="""When the content should be discarded. Defaults to None which means never discarded.""",
    )
    custom: Optional[dict] = Field(
        default_factory=dict,
        description="""Optional dict for storing any other required custom properties of the content.""",
    )


class Event(BaseModel):
    name: str = Field(description="""Unique name of the event.""")
    args: Optional[Any] = Field(description="""Optional arguments included with the event.""")


class ConfigurationSetting(BaseModel):
    name: str = Field(description="""Unique name of the configuration setting.""")
    value: Any = Field(description="""Value of the configuration setting.""")
    documentation: Optional[str] = Field(description="""Documentation that explains the configuration setting.""")


class AnalysisRequestQueryModel(BaseModel):
    owner: str
    amt: str
    timeout: int
    version: Optional[str] = None
    extended_version: Optional[list[str]] = []


class AlertListModel(BaseModel):
    root_uuids: list[str]


class ErrorModel(BaseModel):
    code: str
    details: str


class ApiKeyResponseModel(BaseModel):
    api_key: str


def custom_json_encoder(obj):
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    else:
        return pydantic_encoder(obj)


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        return pydantic_encoder(obj)
