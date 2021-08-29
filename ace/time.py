# vim: sw=4:ts=4:et:cc=120
#

import datetime
import re

import pytz
import tzlocal

# the expected format of the event_time of an alert
event_time_format_tz = "%Y-%m-%d %H:%M:%S %z"
# the old time format before we started storing timezones
event_time_format = "%Y-%m-%d %H:%M:%S"
# the "ISO 8601" format that ACE uses to store datetime objects in JSON with a timezone
# NOTE this is the preferred format
event_time_format_json_tz = "%Y-%m-%dT%H:%M:%S.%f%z"
# the "ISO 8601" format that ACE uses to store datetime objects in JSON without a timezone
event_time_format_json = "%Y-%m-%dT%H:%M:%S.%f"

RE_ET_FORMAT = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2} [+-][0-9]{4}$")
RE_ET_OLD_FORMAT = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$")
RE_ET_JSON_FORMAT = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3,6}[+-][0-9]{4}$")
RE_ET_OLD_JSON_FORMAT = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3,6}$")
RE_ET_ISO_FORMAT = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3,6}[+-][0-9]{2}:[0-9]{2}$"
)


def parse_datetime_string(event_time):
    """Return the datetime object for the given event_time."""
    # remove any leading or trailing whitespace
    event_time = event_time.strip()

    if RE_ET_FORMAT.match(event_time):
        return datetime.datetime.strptime(event_time, event_time_format_tz).astimezone(pytz.utc)
    elif RE_ET_OLD_FORMAT.match(event_time):
        return (
            tzlocal.get_localzone()
            .localize(datetime.datetime.strptime(event_time, event_time_format))
            .astimezone(pytz.utc)
        )
    elif RE_ET_JSON_FORMAT.match(event_time):
        return datetime.datetime.strptime(event_time, event_time_format_json_tz).astimezone(pytz.utc)
    elif RE_ET_ISO_FORMAT.match(event_time):
        # we just need to remove the : in the timezone specifier
        # this has been fixed in python 3.7
        event_time = event_time[: event_time.rfind(":")] + event_time[event_time.rfind(":") + 1 :]
        return datetime.datetime.strptime(event_time, event_time_format_json_tz).astimezone(pytz.utc)
    elif RE_ET_OLD_JSON_FORMAT.match(event_time):
        return (
            tzlocal.get_localzone()
            .localize(datetime.datetime.strptime(event_time, event_time_format_json))
            .astimezone(pytz.utc)
        )
    else:
        raise ValueError("invalid date format {}".format(event_time))


def utc_now():
    """Returns datetime.datetime.now() in UTC time zone."""
    return datetime.datetime.now(pytz.utc)
