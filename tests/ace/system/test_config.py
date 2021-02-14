# vim: sw=4:ts=4:et:cc=120

import os

from ace.system.config import (
    DEFAULT_DOC,
    delete_config,
    get_config_documentation,
    get_config_value,
    set_config,
    set_config_documentation,
    set_config_value,
)

import pytest


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
def test_config_set_get(value):
    # should be missing to start
    assert get_config_value("/test") is None

    # set with just value
    set_config("/test", value)
    assert get_config_value("/test") == value

    # docs should be missing
    assert get_config_documentation("/test") == DEFAULT_DOC

    # set the documentation (but not the value)
    set_config_documentation("/test", "test docs")
    assert get_config_value("/test") == value  # value should stay the same
    assert get_config_documentation("/test") == "test docs"

    # set the value (but not the docs)
    set_config_value("/test", value)
    assert get_config_value("/test") == value
    assert get_config_documentation("/test") == "test docs"  # docs should stay the same

    # delete the config entry
    assert delete_config("/test")
    assert get_config_value("/test") is None
    assert get_config_documentation("/test") is None


@pytest.mark.unit
def test_config_default_value():
    assert get_config_value("/test", None) is None
    assert get_config_value("/test", "test") == "test"


@pytest.mark.unit
def test_config_missing_value():
    with pytest.raises(ValueError):
        set_config_value("/test", None)


@pytest.mark.unit
def test_config_env_value():
    os.environ["ACE_TEST"] = "test"

    # without the setting it should return what is in the env var
    assert get_config_value("/test", env="ACE_TEST") == "test"

    # but when it gets set it should return that
    set_config("/test", "that")
    assert get_config_value("/test") == "that"
