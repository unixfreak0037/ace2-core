# vim: ts=4:sw=4:et:cc=120
#
#
#

from typing import Optional, Any

from ace import coreapi
from ace.data_model import Event
from ace.logging import get_logger
from ace.system.events import EventHandler


class EventBaseInterface:
    @coreapi
    async def register_event_handler(self, event: str, handler: EventHandler):
        get_logger().debug(f"registering event handler for {event}: {handler}")
        return await self.i_register_event_handler(event, handler)

    async def i_register_event_handler(self, event: str, handler: EventHandler):
        """Adds an EventHandler for the given event.
        If this handler is already installed for this event then no action is taken."""

        raise NotImplementedError()

    @coreapi
    async def remove_event_handler(self, handler: EventHandler, events: Optional[list[str]] = []):
        get_logger().debug(f"removing event handler {handler}")
        return await self.i_remove_event_handler(handler, events)

    async def i_remove_event_handler(self, handler: EventHandler, events: Optional[list[str]] = []):
        """Removes an EventHandler. The handler is removed from the events specified, or all events if none are specified."""
        raise NotImplementedError()

    @coreapi
    async def get_event_handlers(self, event: str) -> list[EventHandler]:
        return await self.i_get_event_handlers(event)

    async def i_get_event_handlers(self, event: str) -> list[EventHandler]:
        """Returns the list of registered event handlers for the given event."""
        raise NotImplementedError()

    @coreapi
    async def fire_event(self, event: str, event_args: Optional[Any] = None):
        """Fires the event with the given JSON argument."""
        assert isinstance(event, str) and event

        get_logger().debug(f"fired event {event}")
        return await self.i_fire_event(Event(name=event, args=event_args))

    async def i_fire_event(self, event: Event):
        """Calls all registered event handlers for the given event.
        There is no requirement that handlers are called in any particular order."""
        raise NotImplementedError()
