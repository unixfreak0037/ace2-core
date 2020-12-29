# vim: sw=4:ts=4:et:cc=120

import datetime
import uuid
from typing import Optional, Any

from ace.time import utc_now

from pydantic import BaseModel, Field


class DetectionPointModel(BaseModel):
    description: str
    details: Optional[str] = None

    def __hash__(self):
        return hash(self.description + self.details if self.details is not None else "")


class DetectableObjectModel(BaseModel):
    detections: Optional[list[DetectionPointModel]] = Field(default_factory=list)  # XXX set


class TaggableObjectModel(BaseModel):
    tags: Optional[list[str]] = Field(default_factory=list)


class AnalysisModuleTypeModel(BaseModel):
    name: str
    description: str
    observable_types: list[str] = Field(default_factory=list)  # XXX set
    directives: list[str] = Field(default_factory=list)  # XXX set
    dependencies: list[str] = Field(default_factory=list)  # XXX set
    tags: list[str] = Field(default_factory=list)  # XXX set
    modes: list[str] = Field(default_factory=list)  # XXX set
    version: str = "1.0.0"
    timeout: int = 30
    cache_ttl: Optional[int] = None
    additional_cache_keys: list[str] = Field(default_factory=list)
    types: list[str] = Field(default_factory=list)  # XXX set


class AnalysisModel(DetectableObjectModel, TaggableObjectModel, BaseModel):
    uuid: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    type: Optional[AnalysisModuleTypeModel] = None
    observable_id: Optional[str] = None
    observable_ids: Optional[list[str]] = Field(default_factory=list)  # XXX set
    summary: Optional[str] = None
    details: Optional[Any] = None


class ObservableModel(DetectableObjectModel, TaggableObjectModel, BaseModel):
    uuid: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str
    value: str
    time: Optional[datetime.datetime] = Field(default_factory=utc_now)
    analysis: Optional[dict[str, AnalysisModel]] = Field(default_factory=dict)
    directives: Optional[set[str]] = Field(default_factory=set)
    redirection: Optional[str] = None
    links: Optional[set[str]] = Field(default_factory=set)
    limited_analysis: Optional[set[str]] = Field(default_factory=set)
    excluded_analysis: Optional[set[str]] = Field(default_factory=set)
    relationships: Optional[dict[str, set[str]]] = Field(default_factory=dict)
    grouping_target: Optional[bool] = False
    request_tracking: Optional[dict[str, str]] = Field(default_factory=dict)


class RootAnalysisModel(AnalysisModel, BaseModel):
    tool: Optional[str] = None
    tool_instance: Optional[str] = None
    alert_type: Optional[str] = None
    description: Optional[str] = None
    event_time: Optional[datetime.datetime] = Field(default_factory=utc_now)
    name: Optional[str] = None
    state: Optional[dict] = Field(default_factory=dict)
    analysis_mode: Optional[str] = None
    queue: Optional[str] = None
    instructions: Optional[str] = None
    version: Optional[int] = 0
    expires: Optional[bool] = False
    analysis_cancelled: Optional[bool] = False
    analysis_cancelled_reason: Optional[str]
    observable_store: Optional[dict[str, ObservableModel]]
