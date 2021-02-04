# vim: sw=4:ts=4:et:cc=120

import json
import uuid

from typing import Any, Union

import ace

from ace.analysis import RootAnalysis
from ace.system.database import get_db
from ace.system.database.schema import RootAnalysisTracking, AnalysisDetailsTracking
from ace.system.analysis_tracking import AnalysisTrackingInterface, UnknownRootAnalysisError

import sqlalchemy.exc
from sqlalchemy.sql import exists, and_


class DatabaseAnalysisTrackingInterface(AnalysisTrackingInterface):
    def get_root_analysis(self, uuid: str) -> Union[RootAnalysisTracking, None]:
        """Returns the root for the given uuid or None if it does not exist.."""
        result = get_db().query(RootAnalysisTracking).filter(RootAnalysisTracking.uuid == uuid).one_or_none()
        if not result:
            return None

        # we keep a copy of the actual value of the version property in the database
        # (the JSON would have a copy of the previous value)
        # also see update_root_analysis
        root = RootAnalysis.from_json(result.json_data)
        root.version = result.version
        return root

    def track_root_analysis(self, root: RootAnalysis) -> bool:
        """Tracks the given root to the given RootAnalysis uuid."""
        version = root.version
        if version is None:
            version = str(uuid.uuid4())

        try:
            get_db().execute(
                RootAnalysisTracking.__table__.insert().values(
                    uuid=root.uuid, version=version, json_data=root.to_json(exclude_analysis_details=True)
                )
            )
            get_db().commit()
            root.version = version
            return True
        except sqlalchemy.exc.IntegrityError:
            return False

    def update_root_analysis(self, root: RootAnalysis) -> bool:
        # when we update we also update the version
        new_version = str(uuid.uuid4())
        result = get_db().execute(
            RootAnalysisTracking.__table__.update().values(
                version=new_version, json_data=root.to_json(exclude_analysis_details=True)
            )
            # so the version has to match for the update to work
            .where(and_(RootAnalysisTracking.uuid == root.uuid, RootAnalysisTracking.version == root.version))
        )
        get_db().commit()
        if result.rowcount == 0:
            # if the version doesn't match then the update fails
            return False

        root.version = new_version
        return True

    def root_analysis_exists(self, root: str) -> bool:
        return get_db().query(exists().where(RootAnalysisTracking.uuid == root)).scalar()

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

    def analysis_details_exists(self, uuid: str) -> bool:
        return get_db().query(exists().where(AnalysisDetailsTracking.uuid == uuid)).scalar()
