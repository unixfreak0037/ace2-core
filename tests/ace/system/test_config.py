# vim: sw=4:ts=4:et:cc=120

import os

import pytest


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.parametrize(
    "value",
    [
        "test",
        1,
        1.0,
        True,
        False,
        # None,
        [1, 2, 3],
        {"hello": "world"},
    ],
)
async def test_config_set_get(value, system):
    # should be missing to start
    assert await system.get_config_value("/test") is None

    # set value
    await system.set_config("/test", value)
    assert await system.get_config_value("/test") == value

    # docs should be missing
    assert (await system.get_config("/test")).documentation is None

    # set with documentation
    await system.set_config("/test", value, "test docs")
    assert await system.get_config_value("/test") == value  # value should stay the same
    assert (await system.get_config("/test")).documentation == "test docs"

    # delete the config entry
    assert await system.delete_config("/test")
    assert await system.get_config_value("/test") is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_config_default_value(system):
    assert await system.get_config_value("/test", None) is None
    assert await system.get_config_value("/test", "test") == "test"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_config_missing_value(system):
    with pytest.raises(ValueError):
        await system.set_config("/test", None)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_config_env_value(system):
    os.environ["ACE_TEST"] = "test"

    # without the setting it should return what is in the env var
    assert await system.get_config_value("/test", env="ACE_TEST") == "test"

    # but when it gets set it should return that
    await system.set_config("/test", "that")
    assert await system.get_config_value("/test") == "that"
