# vim: ts=4:sw=4:et:cc=120:tw=120

from typing import Optional, Any

from ace.data_model import ConfigurationSetting
from ace.system import ACESystem


class RemoteConfigurationInterface(ACESystem):
    async def i_get_config(self, key: str) -> ConfigurationSetting:
        # XXX this is kind of weird -- see if you can get rid of this
        from ace.system.database import CONFIG_DB_KWARGS, CONFIG_DB_URL

        if key in [CONFIG_DB_URL, CONFIG_DB_KWARGS]:
            return None

        return await self.get_api().get_config(key)

    async def set_config(self, key: str, value: Any, documentation: Optional[str] = None):
        return await self.get_api().set_config(key, value, documentation)

    async def delete_config(self, key: str) -> bool:
        return await self.get_api().delete_config(key)
