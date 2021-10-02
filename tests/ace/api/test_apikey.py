import uuid

from ace.api.apikey import ApiKey

import pytest

key_value = "5dbc0b66-fcf7-4b98-a0f4-59e523dbba92"
key_name = "test"
key_description = "test description"
key_is_admin = False


@pytest.mark.parametrize(
    "key",
    [
        ApiKey(api_key=key_value, name=key_name, description=key_description, is_admin=key_is_admin),
        ApiKey(api_key=key_value, name=key_name, description=key_description),
        ApiKey(api_key=key_value, name=key_name),
    ],
)
@pytest.mark.unit
def test_ApiKey(key):
    model = key.to_model()
    assert model.api_key == key.api_key
    assert model.name == key.name
    assert model.description == key.description
    assert model.is_admin == key.is_admin

    assert key == ApiKey(**key.to_model().dict())
    assert key == ApiKey.from_dict(key.to_dict())
    assert key == ApiKey.from_json(key.to_json())


@pytest.mark.unit
def test_invalid_ApiKey():
    with pytest.raises(TypeError):
        ApiKey()

    with pytest.raises(TypeError):
        ApiKey(api_key=key_value)

    with pytest.raises(TypeError):
        ApiKey(api_key=key_value, name="")
