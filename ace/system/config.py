# vim: ts=4:sw=4:et:cc=120
#
# global system components

import logging
from typing import Any, Optional

from ace.system import get_system, ACESystemInterface
from ace.system.constants import EVENT_CONFIG_SET
from ace.system.events import fire_event


class ConfigurationInterface(ACESystemInterface):
    def get_config(self, key: str) -> Any:
        raise NotImplementedError()

    def set_config(self, key: str, value: Any):
        raise NotImplementedError()


def get_config(key: str, default: Optional[Any] = None) -> Any:
    return get_system().config.get_config(key, default)


def set_config(key: str, value: Any):
    logging.debug(f"modified config key {key}")
    result = get_system().config.set_config(key, value)
    fire_event(EVENT_CONFIG_SET, key, value)
    return result
