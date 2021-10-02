from dataclasses import dataclass, asdict
from typing import Optional

from ace.data_model import ApiKeyModel


@dataclass
class ApiKey:

    # the api key value
    api_key: str
    # the unique name of the api key
    name: str
    # optional description of the api key
    description: Optional[str] = None
    # is this an admin key?
    is_admin: bool = False

    def __post_init__(self):
        if not self.name:
            raise TypeError("name must be a non-zero length string")

    #
    # json serialization
    #

    def to_model(self, *args, **kwargs) -> ApiKeyModel:
        return ApiKeyModel(**asdict(self))

    def to_dict(self, *args, **kwargs) -> dict:
        return self.to_model(*args, **kwargs).dict()

    def to_json(self, *args, **kwargs) -> str:
        return self.to_model(*args, **kwargs).json()

    @staticmethod
    def from_dict(value: dict) -> "ApiKey":
        data = ApiKeyModel(**value)
        return ApiKey(**data.dict())

    @staticmethod
    def from_json(value: str) -> "AnalysisModuleType":
        assert isinstance(value, str)
        return ApiKey.from_dict(ApiKeyModel.parse_raw(value).dict())
