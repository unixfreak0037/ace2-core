# vim: ts=4:sw=4:et:cc=120

import threading

from typing import Optional

from ace.data_model import Event, custom_json_encoder
from ace.system import get_logger, ACESystem
from ace.system.events import EventHandler


class RedisEventInterface(ACESystem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rc = None
        self._rc_p = None
        self.event_sync_lock = threading.RLock()
        self.event_handlers = {}  # key = event.name, value = [EventHandler]
        self.event_thread = None

    def redis_message_handler(self, message: dict):
        if message["type"] not in ["message", "pmessage"]:
            get_logger().debug(f"redis message {message['data']}")
            return

        # decode into utf8
        channel = message["channel"].decode()
        data = message["data"].decode()

        get_logger().debug(f"received channel {message['channel']} data {message['data']}")

        if channel not in self.event_handlers:
            get_logger().warning(f"event {channel} fired but not registered")
            return

        event = Event.parse_raw(data)
        if event.name != channel:
            get_logger().error(f"redis channel {channel} does not match event name {event.name}")
            return

        # grab a copy of a list of the handlers for this event
        with self.event_sync_lock:
            handlers = self.event_handlers[channel][:]

        for handler in handlers:
            try:
                # TODO this should fire on another thread
                handler.handle_event(event)
            except Exception as e:
                try:
                    handler.handle_exception(event, e)
                except Exception as oh_noes:
                    get_logger().error(f"unable to handle exception {e}: {oh_noes}")

    async def i_register_event_handler(self, event: str, handler: EventHandler):
        with self.event_sync_lock:
            # have we initialize our connection to redis pub/sub yet?
            # we can't do this until we've got something registered
            if self._rc is None:
                get_logger().debug("connecting to redis")
                self._rc = self.get_redis_connection()
                self._rc_p = self._rc.pubsub(ignore_subscribe_messages=True)

            if event not in self.event_handlers:
                self.event_handlers[event] = []

            if handler in self.event_handlers[event]:
                get_logger().warning(f"duplicate event handler registration for {event}: {handler}")
                return

            self.event_handlers[event].append(handler)
            redis_handlers = {event: self.redis_message_handler for event, _ in self.event_handlers.items()}

            # XXX assuming we can safely resubscribe every time
            result = self._rc_p.subscribe(**redis_handlers)
            if self.event_thread is None:
                self.event_thread = self._rc_p.run_in_thread(sleep_time=0.001)
                get_logger().debug(f"started redis event thread {self.event_thread}")

    async def i_remove_event_handler(self, handler: EventHandler, events: Optional[list[str]] = []):
        # if we didn't specify which events to remove the handler from then we
        # look at all of them
        with self.event_sync_lock:
            if not events:
                events = list(self.event_handlers.keys())

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

    async def i_get_event_handlers(self, event: str) -> list[EventHandler]:
        with self.event_sync_lock:
            try:
                return self.event_handlers[event][:]
            except KeyError:
                return []

    async def i_fire_event(self, event: Event):
        try:
            with self.get_redis_connection() as rc:
                rc.publish(event.name, event.json(encoder=custom_json_encoder))
        except Exception as e:
            get_logger().error(f"unable to submit event {event} to redis: {e}")

    def stop(self):
        if self.event_thread:
            self.event_thread.stop()
            self.event_thread = None

        super().stop()

    async def reset(self):
        await super().reset()
        # unsubscribe from all events
        if self._rc_p:
            self._rc_p.unsubscribe()
            # self._rc_p = None

        # if self._rc:
        # self._rc.close()
        # self._rc = None

        self.event_handlers = {}  # key = event.name, value = [EventHandler]
