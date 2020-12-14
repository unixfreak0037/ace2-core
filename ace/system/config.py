# vim: ts=4:sw=4:et:cc=120
#
# global system components

from typing import Any

from ace.system import get_system, ACESystemInterface

class ConfigurationInterface(ACESystemInterface):
    def get_config(self, key:str) -> Any:
        raise NotImplementedError()

    def set_config(self, key:str, value: Any):
        raise NotImplementedError()

def get_config(self, key:str) -> Any:
    return get_system().config.get_config(key)

def set_config(self, key: str, value: Any):
    return get_system().config.set_config(key, value)
