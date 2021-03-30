# vim: ts=4:sw=4:et:cc=120

from typing import Any, Optional

from ace.data_model import ConfigurationSetting
from ace.system.base import ConfigurationBaseInterface
from ace.system.database.schema import Config

#
# we store the json of the entire ConfigurationInterface object in the value field of the config table
# rather than just storing the value
# makes it easier to serialize using pydantic
#


class DatabaseConfigurationInterface(ConfigurationBaseInterface):

    temp_config = {}  # key = config path, value = ConfigurationSetting

    def get_config_obj(self, key: str) -> Config:
        with self.get_db() as db:
            return db.query(Config).filter(Config.key == key).one_or_none()

    async def i_get_config(self, key: str) -> ConfigurationSetting:
        # this happens when the system first starts up as it collects the configuration of the database
        with self.get_db() as db:
            if db is None:
                return self.temp_config.get(key, None)

        result = self.get_config_obj(key)
        if result is None:
            return None

        # note that we're storing the entire ConfigurationSetting object in the column
        setting = ConfigurationSetting.parse_raw(result.value)
        setting.documentation = result.documentation
        return setting

    async def i_set_config(self, key: str, value: Any, documentation: Optional[str] = None):
        setting = ConfigurationSetting(name=key, value=value)
        encoded_value = setting.json()

        config = Config(key=key, value=encoded_value, documentation=documentation)
        with self.get_db() as db:
            if db is None:
                self.temp_config[key] = setting
            else:
                db.merge(config)
                db.commit()

    async def i_delete_config(self, key: str) -> bool:
        with self.get_db() as db:
            if db is None:
                return self.temp_config.pop(key) is not None

            result = db.execute(Config.__table__.delete().where(Config.key == key)).rowcount
            db.commit()

        return result == 1
