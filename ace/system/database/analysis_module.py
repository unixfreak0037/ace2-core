# vim: ts=4:sw=4:et:cc=120

import json

from typing import Union, List

import ace
import ace.database.schema

from ace.analysis import AnalysisModuleType
from ace.database.schema import AnalysisModuleTracking
from ace.system.analysis_module import AnalysisModuleTrackingInterface


class DatabaseAnalysisModuleTrackingInterface(AnalysisModuleTrackingInterface):
    def track_analysis_module_type(self, amt: AnalysisModuleType):
        assert isinstance(amt, AnalysisModuleType)
        db_amt = AnalysisModuleTracking(name=amt.name, json_data=amt.to_json())

        ace.db.merge(db_amt)
        ace.db.commit()

    def get_analysis_module_type(self, name: str) -> Union[AnalysisModuleType, None]:
        db_amt = ace.db.query(AnalysisModuleTracking).filter(AnalysisModuleTracking.name == name).one_or_none()

        if db_amt is None:
            return None

        return AnalysisModuleType.from_dict(json.loads(db_amt.json_data))

    def get_all_analysis_module_types(self) -> list[AnalysisModuleType]:
        return [
            AnalysisModuleType.from_dict(json.loads(_.json_data)) for _ in ace.db.query(AnalysisModuleTracking).all()
        ]
