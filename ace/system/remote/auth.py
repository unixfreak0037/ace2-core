# vim: ts=4:sw=4:et:cc=120

from typing import Optional

from ace.system import ACESystem


class RemoteAuthenticationInterface(ACESystem):
    async def create_api_key(
        self, name: str, description: Optional[str] = None, is_admin: Optional[bool] = False
    ) -> str:
        return await self.get_api().create_api_key(name, description, is_admin)

    async def delete_api_key(self, name: str) -> str:
        return await self.get_api().delete_api_key(name)
