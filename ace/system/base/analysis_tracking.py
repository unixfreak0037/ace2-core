# vim: ts=4:sw=4:et:cc=120
#
#
#

import json

from typing import Union, Any

from ace import coreapi
from ace.analysis import RootAnalysis
from ace.logging import get_logger
from ace.constants import *
from ace.crypto import encrypt_chunk, decrypt_chunk

CONFIG_ANALYSIS_ENCRYPTION_ENABLED = "/core/analysis/encrypted"


class AnalysisTrackingBaseInterface:
    async def analysis_encryption_enabled(self) -> bool:
        """Returns True if encryption is configured and analysis is configured to be encrypted."""
        # the settings need to be configured
        if self.encryption_settings is None:
            return False

        # and the key needs to be loaded
        if self.encryption_settings.aes_key is None:
            return False

        # and this needs to return True
        return await self.get_config_value(CONFIG_ANALYSIS_ENCRYPTION_ENABLED, False)

    @coreapi
    async def get_root_analysis(self, root: Union[RootAnalysis, str]) -> Union[RootAnalysis, None]:
        """Returns the loaded RootAnalysis for the given RootAnalysis or uuid, or None if it does not exist."""
        assert isinstance(root, RootAnalysis) or isinstance(root, str)

        if isinstance(root, RootAnalysis):
            root = root.uuid

        get_logger().debug(f"getting root analysis uuid {root}")
        result = await self.i_get_root_analysis(root)
        if result:
            result.system = self

        return result

    async def i_get_root_analysis(self, uuid: str) -> Union[RootAnalysis, None]:
        """Returns the root for the given uuid or None if it does not exist.."""
        raise NotImplementedError()

    @coreapi
    async def track_root_analysis(self, root: RootAnalysis) -> bool:
        """Inserts or updates the root analysis. Returns True if either operation is successfull."""
        assert isinstance(root, RootAnalysis)

        if root.uuid is None:
            raise ValueError(f"uuid property of {root} is None in track_root_analysis")

        get_logger().debug(f"tracking root {root}")
        if not await self.i_track_root_analysis(root):
            return await self.update_root_analysis(root)

        # make sure storage content is tracked to their roots
        for observable in root.get_observables_by_type("file"):
            await self.track_content_root(observable.value, root)

        await self.fire_event(EVENT_ANALYSIS_ROOT_NEW, root)
        return True

    async def i_track_root_analysis(self, root: RootAnalysis) -> bool:
        """Tracks the root analysis, returns True if it worked. Updates the
        version property of the root."""
        raise NotImplementedError()

    @coreapi
    async def update_root_analysis(self, root: RootAnalysis) -> bool:
        assert isinstance(root, RootAnalysis)

        if root.uuid is None:
            raise ValueError(f"uuid property of {root} is None in update_root_analysis")

        get_logger().debug(f"updating root {root} with version {root.version}")
        if not await self.i_update_root_analysis(root):
            return False

        # make sure storage content is tracked to their roots
        for observable in root.get_observables_by_type("file"):
            await self.track_content_root(observable.value, root)

        await self.fire_event(EVENT_ANALYSIS_ROOT_MODIFIED, root)
        return True

    async def i_update_root_analysis(self, root: RootAnalysis) -> bool:
        """Updates the root. Returns True if the update was successful, False
        otherwise. Updates the version property of the root.

        The version of the root passed in must match the version on record for
        the update to work."""
        raise NotImplementedError()

    @coreapi
    async def delete_root_analysis(self, root: Union[RootAnalysis, str]) -> bool:
        assert isinstance(root, RootAnalysis) or isinstance(root, str)

        if isinstance(root, RootAnalysis):
            root = root.uuid

        get_logger().debug(f"deleting root {root}")
        result = await self.i_delete_root_analysis(root)
        if result:
            await self.fire_event(EVENT_ANALYSIS_ROOT_DELETED, root)

        return result

    async def i_delete_root_analysis(self, uuid: str) -> bool:
        """Deletes the given RootAnalysis JSON data by uuid, and any associated analysis details."""
        raise NotImplementedError()

    @coreapi
    async def root_analysis_exists(self, root: Union[RootAnalysis, str]) -> bool:
        assert isinstance(root, RootAnalysis) or isinstance(root, str)

        if isinstance(root, RootAnalysis):
            root = root.uuid

        return await self.i_root_analysis_exists(root)

    async def i_root_analysis_exists(self, uuid: str) -> bool:
        """Returns True if the given root analysis exists, False otherwise."""
        raise NotImplementedError()

    @coreapi
    async def get_analysis_details(self, uuid: str) -> Any:
        assert isinstance(uuid, str)

        details = await self.i_get_analysis_details(uuid)
        if details is None:
            return None

        if await self.analysis_encryption_enabled():
            details = await decrypt_chunk(self.encryption_settings.aes_key, details)

        return json.loads(details.decode())

    async def i_get_analysis_details(self, uuid: str) -> bytes:
        """Returns the details for the given Analysis object, or None if is has not been set."""
        raise NotImplementedError()

    @coreapi
    async def track_analysis_details(self, root: RootAnalysis, uuid: str, value: Any) -> bool:
        assert isinstance(root, RootAnalysis)
        assert isinstance(uuid, str)

        # we don't save Analysis that doesn't have the details set
        if value is None:
            return False

        get_logger().debug(f"tracking {root} analysis details {uuid}")
        exists = await self.analysis_details_exists(root.uuid)

        # the thing to be tracked must be able to serialize into json
        json_value = json.dumps(value, sort_keys=True)

        if await self.analysis_encryption_enabled():
            encoded_value = await encrypt_chunk(self.encryption_settings.aes_key, json_value.encode())
        else:
            encoded_value = json_value.encode()

        await self.i_track_analysis_details(root.uuid, uuid, encoded_value)

        if not exists:
            await self.fire_event(EVENT_ANALYSIS_DETAILS_NEW, [root, root.uuid])
        else:
            await self.fire_event(EVENT_ANALYSIS_DETAILS_MODIFIED, [root, root.uuid])

        return True

    async def i_track_analysis_details(self, root_uuid: str, uuid: str, value: bytes):
        """Tracks the details for the given Analysis object (uuid) in the given root (root_uuid)."""
        raise NotImplementedError()

    @coreapi
    async def delete_analysis_details(self, uuid: str) -> bool:
        assert isinstance(uuid, str)

        get_logger().debug(f"deleting analysis detials {uuid}")
        result = await self.i_delete_analysis_details(uuid)
        if result:
            await self.fire_event(EVENT_ANALYSIS_DETAILS_DELETED, uuid)

        return result

    async def i_delete_analysis_details(self, uuid: str) -> bool:
        """Deletes the analysis details for the given Analysis referenced by id."""
        raise NotImplementedError()

    @coreapi
    async def analysis_details_exists(self, uuid: str) -> bool:
        assert isinstance(uuid, str)
        return await self.i_analysis_details_exists(uuid)

    async def i_analysis_details_exists(self, uuid: str) -> bool:
        """Returns True if the given analysis details exist, False otherwise."""
        raise NotImplementedError()
