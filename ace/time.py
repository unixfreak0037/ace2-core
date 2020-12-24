# vim: sw=4:ts=4:et:cc=120
#

import datetime
import re

from ace.constants import event_time_format_tz, event_time_format, event_time_format_json_tz, event_time_format_json

import pytz
import tzlocal

LOCAL_TIMEZONE = pytz.timezone(tzlocal.get_localzone().zone)

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
        return datetime.datetime.strptime(event_time, event_time_format_tz)
    elif RE_ET_OLD_FORMAT.match(event_time):
        return LOCAL_TIMEZONE.localize(datetime.datetime.strptime(event_time, event_time_format))
    elif RE_ET_JSON_FORMAT.match(event_time):
        return datetime.datetime.strptime(event_time, event_time_format_json_tz)
    elif RE_ET_ISO_FORMAT.match(event_time):
        # we just need to remove the : in the timezone specifier
        # this has been fixed in python 3.7
        event_time = event_time[: event_time.rfind(":")] + event_time[event_time.rfind(":") + 1 :]
        return datetime.datetime.strptime(event_time, event_time_format_json_tz)
    elif RE_ET_OLD_JSON_FORMAT.match(event_time):
        return LOCAL_TIMEZONE.localize(datetime.datetime.strptime(event_time, event_time_format_json))
    else:
        raise ValueError("invalid date format {}".format(event_time))


def utc_now():
    """Returns datetime.datetime.now() in UTC time zone."""
    return LOCAL_TIMEZONE.localize(datetime.datetime.now()).astimezone(pytz.UTC)
