# vim: ts=4:sw=4:et:cc=120

import threading

from typing import Optional

from ace.data_model import Event, custom_json_encoder
from ace.system.events import EventInterface, EventHandler


class ThreadedEventInterafce(EventInterface):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.event_handlers = {}  # key = event, value = [EventHandler]
        self.sync_lock = threading.RLock()

    def register_event_handler(self, event: str, handler: EventHandler):
        with self.sync_lock:
            if event not in self.event_handlers:
                self.event_handlers[event] = []

            if handler not in self.event_handlers[event]:
                self.event_handlers[event].append(handler)

    def remove_event_handler(self, handler: EventHandler, events: Optional[list[str]] = []):
        with self.sync_lock:
            if not events:
                events = self.event_handlers.keys()

            for event in events:
                if handler in self.event_handlers[event]:
                    self.event_handlers[event].remove(handler)

    def get_event_handlers(self, event: str) -> list[EventHandler]:
        with self.sync_lock:
            return self.event_handlers.get(event, [])

    def fire_event(self, event: Event):
        assert isinstance(event, Event)

        # have this go through serialization even though we don't really need to
        # just to stay consistent with how the event system works
        event_json = event.json(encoder=custom_json_encoder)
        event = Event.parse_raw(event_json)

        for handler in self.get_event_handlers(event.name):
            try:
                handler.handle_event(event)
            except Exception as e:
                handler.handle_exception(event, e)

    def reset(self):
        self.event_handlers = {}
