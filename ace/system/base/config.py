# vim: ts=4:sw=4:et:cc=120
#
#
#

import os

from typing import Optional, Any, Union

from ace import coreapi
from ace.constants import *
from ace.logging import get_logger
from ace.data_model import ConfigurationSetting


class ConfigurationBaseInterface:
    async def get_config_value(
        self,
        key: str,
        default: Optional[Any] = None,
        env: Optional[str] = None,
    ) -> Any:
        """Returns the value of the configuration setting.  If the configuration setting is not found and env is not None
        then the OS environment variable in the env parameter is used. Only plain string values can be used with environment
        variables.  Otherwise, default is returned, None if default is not defined."""
        assert isinstance(key, str) and key
        assert env is None or (isinstance(env, str) and str)

        result = await self.get_config(key)
        if result is not None:
            return result.value

        if result is None and env and env in os.environ:
            return os.environ[env]

        return default

    @coreapi
    async def get_config(self, key: str) -> Union[ConfigurationSetting, None]:
        assert isinstance(key, str) and key
        return await self.i_get_config(key)

    async def i_get_config(self, key: str) -> ConfigurationSetting:
        """Returns a ace.data_model.ConfigurationSetting object for the setting, or None if the setting does not
        exist."""
        raise NotImplementedError()

    @coreapi
    async def set_config(self, key: str, value: Any, documentation: Optional[str] = None):
        """Sets the configuration setting. This function updates the setting if it already exists, or creates a new one if
        it did not."""
        assert isinstance(key, str) and key
        assert documentation is None or isinstance(documentation, str) and documentation

        if value is None and documentation is None:
            raise ValueError("cannot set configuration value to None")

        get_logger().debug(f"modified config key {key} value {value}")
        result = await self.i_set_config(key, value, documentation)
        await self.fire_event(EVENT_CONFIG_SET, [key, value, documentation])
        return result

    async def i_set_config(self, key: str, value: Any, documentation: Optional[str] = None):
        """Sets the configuration setting.

        Args:
            key: the configuration setting
            value: any value supported by the pydantic json encoder, values of None are ignored
            documentation: optional free-form documentation for the configuration setting, values of None are ignored

        """

        raise NotImplementedError()

    @coreapi
    async def delete_config(self, key: str) -> bool:
        """Deletes the configuration setting. Returns True if the setting was deleted."""
        assert isinstance(key, str) and key

        get_logger().debug(f"deleted config key {key}")
        result = await self.i_delete_config(key)
        if result:
            await self.fire_event(EVENT_CONFIG_DELETE, key)

        return result

    async def i_delete_config(self, key: str) -> bool:
        """Deletes the configuration setting. Returns True if the configuration setting was deleted, False otherwise."""
        raise NotImplementedError()
