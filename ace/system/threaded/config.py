# vim: ts=4:sw=4:et:cc=120
#

import json

from typing import Any, Optional

from ace.system.config import ConfigurationInterface


class ThreadedConfigurationInterface(ConfigurationInterface):

    config = {}

    def get_config(self, key: str, default: Optional[Any] = None) -> Any:
        result = self.config.get(key, None)
        if result is None:
            return default

        return json.loads(result)

    def set_config(self, key: str, value: Any):
        self.config[key] = json.dumps(value)

    def reset(self):
        self.config = {}
