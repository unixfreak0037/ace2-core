# vim: ts=4:sw=4:et:cc=120

from typing import Optional, Any

from ace.data_model import Event
from ace.system.base import EventBaseInterface
from ace.system.events import EventHandler


class RemoteEventInterface(EventBaseInterface):
    async def register_event_handler(self, event: str, handler: EventHandler):
        raise NotImplementedError()

    async def remove_event_handler(self, handler: EventHandler, events: Optional[list[str]] = []):
        raise NotImplementedError()

    async def get_event_handlers(self, event: str) -> list[EventHandler]:
        raise NotImplementedError()

    async def fire_event(self, event: str, event_args: Optional[Any] = None):
        raise NotImplementedError()
