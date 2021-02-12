# vim: ts=4:sw=4:et:cc=120

from typing import Optional

from ace.data_model import Event, custom_json_encoder
from ace.system import get_logger
from ace.system.events import EventInterface, EventHandler
from ace.system.redis import CONFIG_REDIS_HOST, CONFIG_REDIS_PORT, CONFIG_REDIS_DB, get_redis_connection

from pydantic.json import pydantic_encoder


class RedisEventInterface(EventInterface):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rc = None
        self._rc_p = None
        self.event_handlers = {}  # key = event.name, value = [EventHandler]
        self.event_thread = None

    def redis_message_handler(self, message: dict):
        if message["type"] not in ["message", "pmessage"]:
            get_logger().debug(f"redis message {message['data']}")
            return

        # decode into utf8
        channel = message["channel"].decode()
        data = message["data"].decode()

        if channel not in self.event_handlers:
            get_logger().warning(f"event {channel} fired but not registered")
            return

        event = Event.parse_raw(data)
        if event.name != channel:
            get_logger().error(f"redis channel {channel} does not match event name {event.name}")
            return

        for handler in self.event_handlers[channel]:
            try:
                handler.handle_event(event)
            except Exception as e:
                try:
                    handler.handle_exception(event, e)
                except Exception as oh_noes:
                    get_logger().error(f"unable to handle exception {e}: {oh_noes}")

    def register_event_handler(self, event: str, handler: EventHandler):
        if self._rc is None:
            self._rc = get_redis_connection()
            self._rc_p = self._rc.pubsub(ignore_subscribe_messages=True)

        if event not in self.event_handlers:
            self.event_handlers[event] = []

        if handler in self.event_handlers[event]:
            get_logger().warning(f"duplicate event handler registration for {event}: {handler}")

        self.event_handlers[event].append(handler)

        redis_handlers = {event: self.redis_message_handler for event, _ in self.event_handlers.items()}

        # XXX assuming we can safely resubscribe every time
        self._rc_p.subscribe(**redis_handlers)
        if self.event_thread is None:
            self.event_thread = self._rc_p.run_in_thread(sleep_time=0.001)

    def remove_event_handler(self, handler: EventHandler, events: Optional[list[str]] = []):
        # if we didn't specify which events to remove the handler from then we
        # look at all of them
        if not events:
            events = self.event_handlers.keys()

        for event in events:
            try:
                # remove this hander for this event if it exists
                self.event_handlers[event].remove(handler)
            except ValueError:
                pass

        # determine which events no longer have any handlers
        unsubscribe_events = []
        for event, handlers in self.event_handlers.items():
            if not handlers:
                unsubscribe_events.append(event)

        # unsubscribe from redis for those events
        if unsubscribe_events:
            self._rc_p.unsubscribe(*unsubscribe_events)

    def get_event_handlers(self, event: str) -> list[EventHandler]:
        return self.event_handlers[event]

    def fire_event(self, event: Event):

        try:
            with get_redis_connection() as rc:
                rc.publish(event.name, event.json(encoder=custom_json_encoder))
        except Exception as e:
            get_logger().error(f"unable to submit event {event} to redis: {e}")

    def stop(self):
        if self.event_thread:
            self.event_thread.stop()
