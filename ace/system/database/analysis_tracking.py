# vim: sw=4:ts=4:et:cc=120

import json
import uuid

from typing import Any, Union

import ace

from ace.analysis import RootAnalysis
from ace.system.base import AnalysisTrackingBaseInterface
from ace.system.database.schema import RootAnalysisTracking, AnalysisDetailsTracking
from ace.exceptions import UnknownRootAnalysisError

import sqlalchemy.exc
from sqlalchemy.sql import exists, and_
from sqlalchemy.sql.expression import select, insert, update, delete


class DatabaseAnalysisTrackingInterface(AnalysisTrackingBaseInterface):
    async def i_get_root_analysis(self, uuid: str) -> Union[RootAnalysisTracking, None]:
        """Returns the root for the given uuid or None if it does not exist.."""
        async with self.get_db() as db:
            result = (
                await db.execute(select(RootAnalysisTracking).where(RootAnalysisTracking.uuid == uuid))
            ).one_or_none()

        if not result:
            return None

        # we keep a copy of the actual value of the version property in the database
        # (the JSON would have a copy of the previous value)
        # also see update_root_analysis
        root = RootAnalysis.from_json(result[0].json_data)
        root.version = result[0].version
        return root

    async def i_track_root_analysis(self, root: RootAnalysis) -> bool:
        """Tracks the given root to the given RootAnalysis uuid."""
        version = root.version
        if version is None:
            version = str(uuid.uuid4())

        try:
            async with self.get_db() as db:
                await db.execute(
                    insert(RootAnalysisTracking).values(
                        uuid=root.uuid, version=version, json_data=root.to_json(exclude_analysis_details=True)
                    )
                )
                await db.commit()

            root.version = version
            return True
        except sqlalchemy.exc.IntegrityError:
            return False

    async def i_update_root_analysis(self, root: RootAnalysis) -> bool:
        # when we update we also update the version
        new_version = str(uuid.uuid4())
        async with self.get_db() as db:
            result = await db.execute(
                update(RootAnalysisTracking).values(
                    version=new_version, json_data=root.to_json(exclude_analysis_details=True)
                )
                # so the version has to match for the update to work
                .where(and_(RootAnalysisTracking.uuid == root.uuid, RootAnalysisTracking.version == root.version))
            )
            await db.commit()

        if result.rowcount == 0:
            # if the version doesn't match then the update fails
            return False

        root.version = new_version
        return True

    async def i_root_analysis_exists(self, root: str) -> bool:
        async with self.get_db() as db:
            return (
                await db.execute(select(exists(RootAnalysisTracking)).where(RootAnalysisTracking.uuid == root))
            ).scalar()

    async def i_delete_root_analysis(self, uuid: str) -> bool:
        """Deletes the given RootAnalysis JSON data by uuid, and any associated analysis details."""
        async with self.get_db() as db:
            result = await db.execute(delete(RootAnalysisTracking).where(RootAnalysisTracking.uuid == uuid))
            await db.commit()

        return result.rowcount > 0

    async def i_get_analysis_details(self, uuid: str) -> Any:
        """Returns the details for the given Analysis object, or None if is has not been set."""
        async with self.get_db() as db:
            result = (
                await db.execute(select(AnalysisDetailsTracking).where(AnalysisDetailsTracking.uuid == uuid))
            ).one_or_none()

        if not result:
            return None

        return json.loads(result[0].json_data)

    async def i_track_analysis_details(self, root_uuid: str, uuid: str, value: Any):
        """Tracks the details for the given Analysis object (uuid) in the given root (root_uuid)."""
        try:
            tracking = AnalysisDetailsTracking(
                uuid=uuid, root_uuid=root_uuid, json_data=json.dumps(value, sort_keys=True)
            )

            async with self.get_db() as db:
                await db.merge(tracking)
                await db.commit()

        except sqlalchemy.exc.IntegrityError:
            raise UnknownRootAnalysisError(root_uuid)

    async def i_delete_analysis_details(self, uuid: str) -> bool:
        """Deletes the analysis details for the given Analysis referenced by id."""
        async with self.get_db() as db:
            result = await db.execute(delete(AnalysisDetailsTracking).where(AnalysisDetailsTracking.uuid == uuid))
            await db.commit()

        return result.rowcount > 0

    async def i_analysis_details_exists(self, uuid: str) -> bool:
        async with self.get_db() as db:
            return (
                await db.execute(select(exists(AnalysisDetailsTracking)).where(AnalysisDetailsTracking.uuid == uuid))
            ).scalar()
