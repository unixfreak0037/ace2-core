# vim: sw=4:ts=4:et

import pytz
import tzlocal

# local timezone
LOCAL_TIMEZONE = pytz.timezone(tzlocal.get_localzone().zone)
