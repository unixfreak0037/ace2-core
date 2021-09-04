from dataclasses import dataclass, field
from typing import Optional

from ace.module.base import AnalysisModule
from ace.service.base import ACEService


@dataclass
class ACEPackage:
    source: str
    name: str
    description: str
    version: str

    # the list of AnalysisModule types that this package provides
    modules: Optional[type[AnalysisModule]] = field(default_factory=list)
    services: Optional[type[ACEService]] = field(default_factory=list)
