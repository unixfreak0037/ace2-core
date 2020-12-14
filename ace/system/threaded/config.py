# vim: ts=4:sw=4:et:cc=120
#

from typing import Any

from ace.system.config import ConfigurationInterface

class ThreadedConfigurationInterface(ConfigurationInterface):

    config = {} 

    def get_config(self, key:str) -> Any:
        return self.config.get(key, None)

    def set_config(self, key:str, value: Any):
        self.config[key] = value

    def reset(self):
        self.config = {}
