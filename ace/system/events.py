# vim: ts=4:sw=4:et:cc=120

import dataclasses
import json

from typing import Optional, Any

from ace.data_model import Event
from ace.system import ACESystemInterface, get_system, get_logger

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


class EventInterface(ACESystemInterface):
    def register_event_handler(self, event: str, handler: EventHandler):
        """Adds an EventHandler for the given event.
        If this handler is already installed for this event then no action is taken."""

        raise NotImplementedError()

    def remove_event_handler(self, handler: EventHandler, events: Optional[list[str]] = []):
        """Removes an EventHandler. The handler is removed from the events specified, or all events if none are specified."""
        raise NotImplementedError()

    def get_event_handlers(self, event: str) -> list[EventHandler]:
        """Returns the list of registered event handlers for the given event."""
        raise NotImplementedError()

    def fire_event(self, event: Event):
        """Calls all registered event handlers for the given event.
        There is no requirement that handlers are called in any particular order."""
        raise NotImplementedError()


def register_event_handler(event: str, handler: EventHandler):
    get_logger().debug(f"registering event handler for {event}: {handler}")
    return get_system().events.register_event_handler(event, handler)


def remove_event_handler(handler: EventHandler, events: Optional[list[str]] = []):
    get_logger().debug(f"removing event handler {handler}")
    return get_system().events.remove_event_handler(handler, events)


def get_event_handlers(event: str) -> list[EventHandler]:
    return get_system().events.get_event_handlers(event)


def fire_event(event: str, event_args: Any):
    """Fires the event with the given JSON argument."""
    assert isinstance(event, str) and event

    get_logger().debug(f"fired event {event}")
    return get_system().events.fire_event(Event(name=event, args=event_args))
