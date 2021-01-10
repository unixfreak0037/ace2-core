# vim: sw=4:ts=4:et:cc=120

from ace.system.config import get_config, set_config

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
        None,
        [1, 2, 3],
        {"hello": "world"},
    ],
)
def test_config_set_get(value):
    set_config("/test", value)
    assert get_config("/test") == value


def test_config_default_value():
    assert get_config("/test", None) is None
    assert get_config("/test", "test") == "test"
