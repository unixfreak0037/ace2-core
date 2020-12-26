# vim: sw=4:ts=4:et:cc=120

import ace.time
from ace.time import parse_datetime_string

import pytest


@pytest.mark.unit
def test_parse_datetime_string():
    default_format = "2018-10-19 14:06:34 +0000"
    old_default_format = "2018-10-19 14:06:34"
    json_format = "2018-10-19T18:08:08.346118-05:00"
    old_json_format = "2018-10-19T18:08:08.346118"
    splunk_format = "2015-02-19T09:50:49.000-05:00"

    result = parse_datetime_string(default_format)
    assert result.year == 2018
    assert result.month == 10
    assert result.day == 19
    assert result.hour == 14
    assert result.minute == 6
    assert result.second == 34
    assert result.tzinfo is not None
    assert int(result.tzinfo.utcoffset(None).total_seconds()) == 0

    result = parse_datetime_string(old_default_format)
    assert result.year == 2018
    assert result.month == 10
    assert result.day == 19
    assert result.hour == 14
    assert result.minute == 6
    assert result.second == 34
    assert result.tzinfo is not None

    result = parse_datetime_string(json_format)
    assert result.year == 2018
    assert result.month == 10
    assert result.day == 19
    assert result.hour == 18
    assert result.minute == 8
    assert result.second == 8
    assert result.tzinfo is not None
    assert int(result.tzinfo.utcoffset(None).total_seconds()) == -(5 * 60 * 60)

    result = parse_datetime_string(old_json_format)
    assert result.year == 2018
    assert result.month == 10
    assert result.day == 19
    assert result.hour == 18
    assert result.minute == 8
    assert result.second == 8
    assert result.tzinfo is not None

    result = parse_datetime_string(splunk_format)
    assert result.year == 2015
    assert result.month == 2
    assert result.day == 19
    assert result.hour == 9
    assert result.minute == 50
    assert result.second == 49
    assert result.tzinfo is not None
    assert int(result.tzinfo.utcoffset(None).total_seconds()) == -(5 * 60 * 60)
