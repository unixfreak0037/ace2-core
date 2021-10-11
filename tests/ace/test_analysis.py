import datetime

from ace.analysis import RootAnalysis
from ace.time import event_time_format_tz, event_time_format

from tests.ace.test_time import mock_tz

import pytest
import pytz


@pytest.mark.parametrize(
    "source_time,expected_time",
    [
        # None
        (None, None),
        # with UTC timezone
        (
            datetime.datetime(2021, 12, 12, 1, 0, 0, tzinfo=pytz.utc),
            datetime.datetime(2021, 12, 12, 1, 0, 0, tzinfo=pytz.utc),
        ),
        # without a timezone
        (datetime.datetime(2021, 12, 12, 1, 0, 0), datetime.datetime(2021, 12, 12, 2, 0, 0, tzinfo=pytz.utc)),
        # string with UTC timezone
        (
            datetime.datetime(2021, 12, 12, 1, 0, 0, tzinfo=pytz.utc).strftime(event_time_format_tz),
            datetime.datetime(2021, 12, 12, 1, 0, 0, tzinfo=pytz.utc),
        ),
        # string without timezone
        (
            datetime.datetime(2021, 12, 12, 1, 0, 0).strftime(event_time_format),
            datetime.datetime(2021, 12, 12, 2, 0, 0, tzinfo=pytz.utc),
        ),
    ],
)
@pytest.mark.unit
def test_set_event_time(source_time, expected_time, mock_tz):
    root = RootAnalysis()
    root.event_time = source_time
    assert root.event_time == expected_time
