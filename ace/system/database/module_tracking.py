# vim: ts=4:sw=4:et:cc=120

import json

from typing import Union, List

import ace

from ace.analysis import AnalysisModuleType
from ace.system.base import AnalysisModuleTrackingBaseInterface
from ace.system.database.schema import AnalysisModuleTracking

from sqlalchemy.sql.expression import select, delete


class DatabaseAnalysisModuleTrackingInterface(AnalysisModuleTrackingBaseInterface):
    async def i_track_analysis_module_type(self, amt: AnalysisModuleType):
        assert isinstance(amt, AnalysisModuleType)
        db_amt = AnalysisModuleTracking(name=amt.name, json_data=amt.to_json())

        async with self.get_db() as db:
            await db.merge(db_amt)
            await db.commit()

    async def i_delete_analysis_module_type(self, amt: AnalysisModuleType):
        assert isinstance(amt, AnalysisModuleType)
        async with self.get_db() as db:
            await db.execute(delete(AnalysisModuleTracking).where(AnalysisModuleTracking.name == amt.name))
            await db.commit()

    async def i_get_analysis_module_type(self, name: str) -> Union[AnalysisModuleType, None]:
        async with self.get_db() as db:
            db_amt = (
                await db.execute(select(AnalysisModuleTracking).where(AnalysisModuleTracking.name == name))
            ).scalar()

            if db_amt is None:
                return None

            return AnalysisModuleType.from_dict(json.loads(db_amt.json_data))

    async def i_get_all_analysis_module_types(self) -> list[AnalysisModuleType]:
        async with self.get_db() as db:
            return [
                AnalysisModuleType.from_dict(json.loads(_[0].json_data))
                for _ in (await db.execute(select(AnalysisModuleTracking))).all()
            ]
