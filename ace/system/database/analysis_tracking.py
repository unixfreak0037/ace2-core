# vim: sw=4:ts=4:et:cc=120

import json

from typing import Any, Union

import ace

from ace.analysis import RootAnalysis
from ace.system.database import get_db
from ace.system.database.schema import RootAnalysisTracking, AnalysisDetailsTracking
from ace.system.analysis_tracking import AnalysisTrackingInterface, UnknownRootAnalysisError

import sqlalchemy.exc


class DatabaseAnalysisTrackingInterface(AnalysisTrackingInterface):
    def get_root_analysis(self, uuid: str) -> Union[RootAnalysisTracking, None]:
        """Returns the root for the given uuid or None if it does not exist.."""
        result = get_db().query(RootAnalysisTracking).filter(RootAnalysisTracking.uuid == uuid).one_or_none()
        if not result:
            return None

        return RootAnalysis.from_json(result.json_data)

    def track_root_analysis(self, root: RootAnalysis):
        """Tracks the given root to the given RootAnalysis uuid."""
        tracking = RootAnalysisTracking(
            uuid=root.uuid,
            json_data=root.to_json(exclude_analysis_details=True),
        )

        get_db().merge(tracking)
        get_db().commit()

    def delete_root_analysis(self, uuid: str) -> bool:
        """Deletes the given RootAnalysis JSON data by uuid, and any associated analysis details."""
        result = get_db().execute(RootAnalysisTracking.__table__.delete().where(RootAnalysisTracking.uuid == uuid))
        get_db().commit()
        return result.rowcount > 0

    def get_analysis_details(self, uuid: str) -> Any:
        """Returns the details for the given Analysis object, or None if is has not been set."""
        result = get_db().query(AnalysisDetailsTracking).filter(AnalysisDetailsTracking.uuid == uuid).one_or_none()
        if not result:
            return None

        return json.loads(result.json_data)

    def track_analysis_details(self, root_uuid: str, uuid: str, value: Any):
        """Tracks the details for the given Analysis object (uuid) in the given root (root_uuid)."""
        try:
            tracking = AnalysisDetailsTracking(
                uuid=uuid, root_uuid=root_uuid, json_data=json.dumps(value, sort_keys=True)
            )

            get_db().merge(tracking)
            get_db().commit()
        except sqlalchemy.exc.IntegrityError:
            raise UnknownRootAnalysisError(root_uuid)

    def delete_analysis_details(self, uuid: str) -> bool:
        """Deletes the analysis details for the given Analysis referenced by id."""
        result = get_db().execute(
            AnalysisDetailsTracking.__table__.delete().where(AnalysisDetailsTracking.uuid == uuid)
        )
        get_db().commit()
        return result.rowcount > 0
