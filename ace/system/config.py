# vim: ts=4:sw=4:et:cc=120:tw=120
#
# global system components

import os
from typing import Any, Optional, Union

from ace.data_model import ConfigurationSetting
from ace.system import get_logger, get_system, ACESystemInterface
from ace.system.constants import EVENT_CONFIG_SET, EVENT_CONFIG_DELETE
from ace.system.events import fire_event

DEFAULT_DOC = "Documentation has not been set for this configuration setting."


class ConfigurationInterface(ACESystemInterface):
    def get_config(self, key: str) -> ConfigurationSetting:
        """Returns a ace.data_model.ConfigurationSetting object for the setting, or None if the setting does not
        exist."""
        raise NotImplementedError()

    def set_config(self, key: str, value: Any, documentation: Optional[str] = None):
        """Sets the configuration setting.

        Args:
            key: the configuration setting
            value: any value supported by the pydantic json encoder, values of None are ignored
            documentation: optional free-form documentation for the configuration setting, values of None are ignored

        """

        raise NotImplementedError()

    def delete_config(self, key: str) -> bool:
        """Deletes the configuration setting. Returns True if the configuration setting was deleted, False otherwise."""
        raise NotImplementedError()


def get_config_value(
    key: str,
    default: Optional[Any] = None,
    env: Optional[str] = None,
) -> Any:
    """Returns the value of the configuration setting.  If the configuration setting is not found and env is not None
    then the OS environment variable in the env parameter is used. Only plain string values can be used with environment
    variables.  Otherwise, default is returned, None if default is not defined."""
    assert isinstance(key, str) and key
    assert env is None or (isinstance(env, str) and str)

    result = get_system().config.get_config(key)
    if result is not None:
        return result.value

    if result is None and env and env in os.environ:
        return os.environ[env]

    return default


def set_config(key: str, value: Any, documentation: Optional[str] = None):
    """Sets the configuration setting. This function updates the setting if it already exists, or creates a new one if
    it did not."""
    assert isinstance(key, str) and key
    assert documentation is None or isinstance(documentation, str) and documentation

    if value is None and documentation is None:
        raise ValueError("cannot set configuration value to None")

    get_logger().debug(f"modified config key {key}")
    result = get_system().config.set_config(key, value, documentation)
    fire_event(EVENT_CONFIG_SET, [key, value, documentation])
    return result


def delete_config(key: str) -> bool:
    """Deletes the configuration setting. Returns True if the setting was deleted."""
    assert isinstance(key, str) and key

    get_logger().debug(f"deleted config key {key}")
    result = get_system().config.delete_config(key)
    if result:
        fire_event(EVENT_CONFIG_DELETE, key)

    return result


def get_config_documentation(key: str) -> Union[str, None]:
    """Returns the documentation for the specified configuration setting. If the configuration setting does not exist
    then None is returned. If the documentation has not been set then the value of ace.system.config.DEFAULT_DOC is
    returned."""
    assert isinstance(key, str) and key

    result = get_system().config.get_config(key)
    if not result:
        return None

    if not result.documentation:
        return DEFAULT_DOC

    return result.documentation


def set_config_documentation(key: str, documentation: str):
    """Sets the documentation for the specified configuration setting.
    The format of the documentation is not specified by the core system."""
    set_config(key, value=None, documentation=documentation)


def set_config_value(key: str, value: str):
    """Sets the configuration value."""
    set_config(key, value, documentation=None)
