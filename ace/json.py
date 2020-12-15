# vim: sw=4:ts=4:et

import datetime
import json

from ace.constants import event_time_format_json_tz

# utility class to translate custom objects into JSON
class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.strftime(event_time_format_json_tz)
        elif isinstance(obj, bytes):
            return obj.decode('unicode_escape', 'replace')
        elif hasattr(obj, 'to_dict'):
            return obj.to_dict()
        else:
            return super(JSONEncoder, self).default(obj)

