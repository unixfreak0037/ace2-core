# vim: ts=4:sw=4:et:cc=120

import dataclasses
import json

from typing import Optional, Any

from ace.system import ACESystemInterface, get_system, get_logger

#
# events
# an event is fired with *args and **kwargs
# an object is created that transports these things to the target handler
#
# {
#   'event': event,
#   'args': [],
#   'kwargs': {},
# }
#
# the arguments are translated into JSON
# any arguments with to_json() functions are translated into JSON using that function
# otherwise default json encoding takes place
#
# event handlers simply receive the JSON
# it is up to the hander to understand how to interpret (decode) the json
#


class EventHandler:
    def handle_event(self, event: str, event_json):
        """Called when an event is fired.

        Args:
            event: the event that fired
            event_json: any additional arguments passed to the event
        """
        raise NotImplementedError()

    def handle_exception(self, event: str, exception: Exception, event_args_json: str):
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

    def fire_event(self, event: str, event_args_json: str):
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

    class _json_encoder(json.JSONEncoder):
        def default(self, obj):
            if hasattr(obj, "to_json"):
                return obj.to_json()
            elif dataclasses.is_dataclass(obj):
                return dataclasses.asdict(obj)
            else:
                json.JSONEncoder.default(self, obj)

    event_args_json = json.dumps(event_args, cls=_json_encoder)
    get_logger().debug(f"fired event {event}")
    return get_system().events.fire_event(event, event_args_json)
