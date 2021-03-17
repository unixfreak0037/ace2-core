# vim: ts=4:sw=4:et:cc=120

from ace.data_model import Event

#
# Events
#
# An event has two properties: name and args.
# name is the identifier of the event (see ace/system/constants.py)
# args is anything that can be encoded into JSON
# ace.data_model.custom_json_encoder is used to encode the JSON
#
# When an even handler receives the event the args property is already decoded
# into a dict. The caller is responsible for decoding the dict. For example, if
# the dict is actually a RootAnalysis object, then the caller must call
# RootAnalysis.from_dict(event.args).
#


class EventHandler:
    def handle_event(self, event: Event):
        """Called when an event is fired.

        Args:
            event: the event that fired
        """
        raise NotImplementedError()

    def handle_exception(self, event: str, exception: Exception):
        """Called when the call to handle_event raises an exception.

        This is called with the same parameters as handle_event and an additional parameter that is the exception that was raised.
        """
        raise NotImplementedError()
