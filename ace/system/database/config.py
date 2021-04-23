# vim: ts=4:sw=4:et:cc=120

from typing import Any, Optional

from ace.logging import get_logger
from ace.data_model import ConfigurationSetting
from ace.system.base import ConfigurationBaseInterface
from ace.system.database.schema import Config

from sqlalchemy.sql.expression import select, delete

#
# we store the json of the entire ConfigurationInterface object in the value field of the config table
# rather than just storing the value
# makes it easier to serialize using pydantic
#


class DatabaseConfigurationInterface(ConfigurationBaseInterface):

    temp_config = {}  # key = config path, value = ConfigurationSetting

    async def get_config_obj(self, key: str) -> Config:
        async with self.get_db() as db:
            return (await db.execute(select(Config).where(Config.key == key))).one_or_none()

    async def i_get_config(self, key: str) -> ConfigurationSetting:
        # this happens when the system first starts up as it collects the configuration of the database
        async with self.get_db() as db:
            if db is None:
                get_logger().debug(f"obtaining config key {key} from temporary memory space")
                return self.temp_config.get(key, None)

        result = await self.get_config_obj(key)
        if result is None:
            return self.temp_config.get(key, None)

        # note that we're storing the entire ConfigurationSetting object in the column
        setting = ConfigurationSetting.parse_raw(result[0].value)
        setting.documentation = result[0].documentation
        return setting

    async def i_set_config(self, key: str, value: Any, documentation: Optional[str] = None):
        setting = ConfigurationSetting(name=key, value=value)
        encoded_value = setting.json()

        config = Config(key=key, value=encoded_value, documentation=documentation)
        async with self.get_db() as db:
            if db is None:
                get_logger().debug(f"storing config key {key} value {setting} into temporary memory space")
                self.temp_config[key] = setting
            else:
                await db.merge(config)
                await db.commit()

    async def i_delete_config(self, key: str) -> bool:
        async with self.get_db() as db:
            if db is None:
                return self.temp_config.pop(key) is not None

            result = (await db.execute(delete(Config).where(Config.key == key))).rowcount
            await db.commit()

        return result == 1
