# vim: ts=4:sw=4:et:cc=120

from typing import Any, Optional

from ace.data_model import ConfigurationSetting
from ace.system.config import ConfigurationInterface
from ace.system.database import get_db
from ace.system.database.schema import Config

#
# we store the json of the entire ConfigurationInterface object in the value field of the config table
# rather than just storing the value
# makes it easier to serialize using pydantic
#


class DatabaseConfigurationInterface(ConfigurationInterface):
    def get_config_obj(self, key: str) -> Config:
        with get_db() as db:
            return db.query(Config).filter(Config.key == key).one_or_none()

    def get_config(self, key: str) -> ConfigurationSetting:
        # this happens when the system first starts up as it collects the configuration of the database
        with get_db() as db:
            if db is None:
                return None

        result = self.get_config_obj(key)
        if result is None:
            return None

        # note that we're storing the entire ConfigurationSetting object in the column
        setting = ConfigurationSetting.parse_raw(result.value)
        setting.documentation = result.documentation
        return setting

    def set_config(self, key: str, value: Any, documentation: Optional[str] = None):
        setting = ConfigurationSetting(name=key, value=value)
        encoded_value = setting.json()

        kwargs = {"key": key}
        if value is not None:
            kwargs["value"] = ConfigurationSetting(name=key, value=value).json()
        if documentation is not None:
            kwargs["documentation"] = documentation

        config = Config(**kwargs)
        with get_db() as db:
            db.merge(config)
            db.commit()

    def delete_config(self, key: str) -> bool:
        with get_db() as db:
            result = db.execute(Config.__table__.delete().where(Config.key == key)).rowcount
            db.commit()
        return result == 1
