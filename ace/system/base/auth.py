# vim: ts=4:sw=4:et:cc=120
#
#
#

from typing import Optional, Union

from ace import coreapi
from ace.api import ApiKey
from ace.exceptions import MissingEncryptionSettingsError


class AuthenticationBaseInterface:
    @coreapi
    async def create_api_key(
        self, name: str, description: Optional[str] = None, is_admin: Optional[bool] = False
    ) -> ApiKey:
        """Creates a new api_key. Returns the newly created api_key."""
        return await self.i_create_api_key(name, description, is_admin)

    async def i_create_api_key(self, name: str, description: Optional[str] = None) -> Union[ApiKey, None]:
        raise NotImplementedError()

    @coreapi
    async def delete_api_key(self, name: str) -> bool:
        """Deletes the given api key. Returns True if the key was deleted, False otherwise."""
        return await self.i_delete_api_key(name)

    async def i_delete_api_key(self, name: str) -> bool:
        raise NotImplementedError()

    @coreapi
    async def verify_api_key(self, api_key: str, is_admin: Optional[bool] = False) -> bool:
        """Returns True if the given api key is valid, False otherwise. If
        is_admin is True then the api_key must also be an admin key to pass
        verification."""
        return await self.i_verify_api_key(api_key, is_admin)

    async def i_verify_api_key(self, api_key: str) -> bool:
        raise NotImplementedError()

    @coreapi
    async def get_api_keys(self) -> list[ApiKey]:
        """Returns all api keys."""
        return await self.i_get_api_keys()

    async def i_get_api_keys(self) -> list[ApiKey]:
        raise NotImplementedError()
