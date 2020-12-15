# vim: ts=4:sw=4:et:cc=120

from typing import Optional

from ace.system import ACESystemInterface, get_system


class EventHandler:
    def handle_event(self, event: str, *args, **kwargs):
        raise NotImplementedError()

    def handle_exception(self, event: str, exception: Exception, *args, **kwargs):
        raise NotImplementedError()


class EventInterface(ACESystemInterface):
    def register_event_handler(self, event: str, handler: EventHandler):
        raise NotImplementedError()

    def remove_event_handler(self, handler: EventHandler, events: Optional[list[str]] = []):
        raise NotImplementedError()

    def get_event_handlers(self, event: str) -> list[EventHandler]:
        raise NotImplementedError()


def register_event_handler(event: str, handler: EventHandler):
    return get_system().events.register_event_handler(event, handler)


def remove_event_handler(handler: EventHandler, events: Optional[list[str]] = []):
    return get_system().events.remove_event_handler(handler, events)


def get_event_handlers(event: str) -> list[EventHandler]:
    return get_system().events.get_event_handlers(event)


def fire_event(event: str, *args, **kwargs):
    for handler in get_event_handlers(event):
        try:
            handler.handle_event(event, *args, **kwargs)
        except Exception as e:
            handler.handle_exception(event, e, *args, **kwargs)
