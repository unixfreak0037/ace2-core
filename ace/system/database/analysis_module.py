# vim: ts=4:sw=4:et:cc=120

import json

from typing import Union, List

import ace

from ace.analysis import AnalysisModuleType
from ace.system.database import get_db
from ace.system.database.schema import AnalysisModuleTracking
from ace.system.analysis_module import AnalysisModuleTrackingInterface


class DatabaseAnalysisModuleTrackingInterface(AnalysisModuleTrackingInterface):
    def track_analysis_module_type(self, amt: AnalysisModuleType):
        assert isinstance(amt, AnalysisModuleType)
        db_amt = AnalysisModuleTracking(name=amt.name, json_data=amt.to_json())

        with get_db() as db:
            db.merge(db_amt)
            db.commit()

    def delete_analysis_module_type(self, amt: AnalysisModuleType):
        assert isinstance(amt, AnalysisModuleType)
        with get_db() as db:
            db.execute(AnalysisModuleTracking.__table__.delete().where(AnalysisModuleTracking.name == amt.name))
            db.commit()

    def get_analysis_module_type(self, name: str) -> Union[AnalysisModuleType, None]:
        with get_db() as db:
            db_amt = db.query(AnalysisModuleTracking).filter(AnalysisModuleTracking.name == name).one_or_none()

            if db_amt is None:
                return None

            return AnalysisModuleType.from_dict(json.loads(db_amt.json_data))

    def get_all_analysis_module_types(self) -> list[AnalysisModuleType]:
        with get_db() as db:
            return [
                AnalysisModuleType.from_dict(json.loads(_.json_data)) for _ in db.query(AnalysisModuleTracking).all()
            ]
