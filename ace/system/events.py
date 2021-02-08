# vim: ts=4:sw=4:et:cc=120

from typing import Optional

from ace.system import ACESystemInterface, get_system, get_logger


class EventHandler:
    def handle_event(self, event: str, *args, **kwargs):
        """Called when an event is fired.

        Args:
            event: the event that fired
            *args, **kwargs: any additional arguments passed to the event
        """
        raise NotImplementedError()

    def handle_exception(self, event: str, exception: Exception, *args, **kwargs):
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


def register_event_handler(event: str, handler: EventHandler):
    get_logger().debug(f"registering event handler for {event}: {handler}")
    return get_system().events.register_event_handler(event, handler)


def remove_event_handler(handler: EventHandler, events: Optional[list[str]] = []):
    get_logger().debug(f"removing event handler {handler}")
    return get_system().events.remove_event_handler(handler, events)


def get_event_handlers(event: str) -> list[EventHandler]:
    return get_system().events.get_event_handlers(event)


def fire_event(event: str, *args, **kwargs):
    """Calls all registered event handlers for the given event.
    There is no requirement that handlers are called in any particular order."""

    get_logger().debug(f"fired event {event}")
    for handler in get_event_handlers(event):
        try:
            handler.handle_event(event, *args, **kwargs)
        except Exception as e:
            handler.handle_exception(event, e, *args, **kwargs)
