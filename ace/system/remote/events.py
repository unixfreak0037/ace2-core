# vim: ts=4:sw=4:et:cc=120

from typing import Optional

from ace.data_model import Event
from ace.system.base import EventBaseInterface
from ace.system.events import EventHandler


class RemoteEventInterface(EventBaseInterface):
    pass
    # async def i_register_event_handler(self, event: str, handler: EventHandler):
    # return await self.get_api().register_event_handler(event, handler)

    # async def i_remove_event_handler(self, handler: EventHandler, events: Optional[list[str]] = []):
    # return await self.get_api().remove_event_handler(handler, events)

    # async def i_get_event_handlers(self, event: str) -> list[EventHandler]:
    # return await self.get_api().get_event_handlers(event)

    # async def i_fire_event(self, event: Event):
    # return await self.get_api().fire_event(event)
