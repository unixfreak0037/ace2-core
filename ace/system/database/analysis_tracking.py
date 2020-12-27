# vim: sw=4:ts=4:et:cc=120

import json

from typing import Any, Union

import ace

from ace.database.schema import RootAnalysisTracking, AnalysisDetailsTracking
from ace.json import JSONEncoder
from ace.system.analysis_tracking import AnalysisTrackingInterface, UnknownRootAnalysisError

import sqlalchemy.exc


class DatabaseAnalysisTrackingInterface(AnalysisTrackingInterface):
    def get_root_analysis(self, uuid: str) -> Union[dict, None]:
        """Returns the root for the given uuid or None if it does not exist.."""
        result = ace.db.query(RootAnalysisTracking).filter(RootAnalysisTracking.uuid == uuid).one_or_none()
        if not result:
            return None

        return json.loads(result.json_data)

    def track_root_analysis(self, uuid: str, root: dict):
        """Tracks the given root to the given RootAnalysis uuid."""
        tracking = RootAnalysisTracking(uuid=uuid, json_data=json.dumps(root, cls=JSONEncoder, sort_keys=True))

        ace.db.merge(tracking)
        ace.db.commit()

    def delete_root_analysis(self, uuid: str) -> bool:
        """Deletes the given RootAnalysis JSON data by uuid, and any associated analysis details."""
        result = ace.db.execute(RootAnalysisTracking.__table__.delete().where(RootAnalysisTracking.uuid == uuid))
        ace.db.commit()
        return result.rowcount > 0

    def get_analysis_details(self, uuid: str) -> Any:
        """Returns the details for the given Analysis object, or None if is has not been set."""
        result = ace.db.query(AnalysisDetailsTracking).filter(AnalysisDetailsTracking.uuid == uuid).one_or_none()
        if not result:
            return None

        return json.loads(result.json_data)

    def track_analysis_details(self, root_uuid: str, uuid: str, value: Any):
        """Tracks the details for the given Analysis object (uuid) in the given root (root_uuid)."""
        try:
            tracking = AnalysisDetailsTracking(
                uuid=uuid, root_uuid=root_uuid, json_data=json.dumps(value, cls=JSONEncoder, sort_keys=True)
            )

            ace.db.merge(tracking)
            ace.db.commit()
        except sqlalchemy.exc.IntegrityError:
            raise UnknownRootAnalysisError(root_uuid)

    def delete_analysis_details(self, uuid: str) -> bool:
        """Deletes the analysis details for the given Analysis referenced by id."""
        result = ace.db.execute(AnalysisDetailsTracking.__table__.delete().where(AnalysisDetailsTracking.uuid == uuid))
        ace.db.commit()
        return result.rowcount > 0
