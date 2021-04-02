# vim: ts=4:sw=4:et:cc=120

import asyncio
import threading

from typing import Optional

from ace.data_model import Event, custom_json_encoder
from ace.logging import get_logger
from ace.system.base import EventBaseInterface
from ace.system.events import EventHandler

REDIS_CHANNEL_EVENTS = "events"


class RedisEventInterface(EventBaseInterface):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.event_reader_connection = None
        self.event_reader_stopped_event = None
        self.event_sync_lock = asyncio.Lock()
        self.event_handlers = {}  # key = event.name, value = [EventHandler]

    async def redis_message_handler(self, message: bytes):
        data = message.decode()
        event = Event.parse_raw(data)
        get_logger().debug(f"received event {event.name}")

        # grab a copy of a list of the handlers for this event
        handlers = []
        async with self.event_sync_lock:
            if event.name in self.event_handlers:
                handlers = self.event_handlers[event.name][:]

        for handler in handlers:
            try:
                get_logger().debug(f"handler {handler} event {event.name}")
                await handler.handle_event(event)
            except Exception as e:
                try:
                    await handler.handle_exception(event, e)
                except Exception as oh_noes:
                    get_logger().error(f"unable to handle exception {e}: {oh_noes}")

    async def event_reader(self, channel):
        while await channel.wait_message():
            message = await channel.get()
            if message:
                await self.redis_message_handler(message)

        get_logger().debug("event reader stopped")
        self.event_reader_stopped_event.set()

    async def initialize_event_reader(self):
        """Starts the event reader loop if it isn't already running."""
        if self.event_reader_connection is None:
            get_logger().debug("starting event reader loop")
            self.event_reader_stopped_event = asyncio.Event()
            self.event_reader_connection = await self._get_redis_connection()
            (channel,) = await self.event_reader_connection.subscribe(REDIS_CHANNEL_EVENTS)
            asyncio.get_running_loop().create_task(self.event_reader(channel))

    async def stop_event_reader(self):
        """Stops the event reader if it's running."""
        if self.event_reader_connection:
            self.event_reader_connection.close()
            await self.event_reader_connection.wait_closed()
            await self.event_reader_stopped_event.wait()

    async def i_register_event_handler(self, event: str, handler: EventHandler):

        # make sure the event reader has started
        await self.initialize_event_reader()

        async with self.event_sync_lock:
            # have we initialize our connection to redis pub/sub yet?
            # we can't do this until we've got something registered
            if event not in self.event_handlers:
                self.event_handlers[event] = []

            if handler in self.event_handlers[event]:
                get_logger().warning(f"duplicate event handler registration for {event}: {handler}")
                return

            self.event_handlers[event].append(handler)
            redis_handlers = {event: self.redis_message_handler for event, _ in self.event_handlers.items()}

    async def i_remove_event_handler(self, handler: EventHandler, events: Optional[list[str]] = []):
        # if we didn't specify which events to remove the handler from then we
        # look at all of them
        async with self.event_sync_lock:
            if not events:
                events = list(self.event_handlers.keys())

            for event in events:
                try:
                    # remove this hander for this event if it exists
                    self.event_handlers[event].remove(handler)
                except ValueError:
                    pass

    async def i_get_event_handlers(self, event: str) -> list[EventHandler]:
        async with self.event_sync_lock:
            try:
                return self.event_handlers[event][:]
            except KeyError:
                return []

    async def i_fire_event(self, event: Event):
        try:
            async with self.get_redis_connection() as rc:
                await rc.publish(REDIS_CHANNEL_EVENTS, event.json(encoder=custom_json_encoder))
        except Exception as e:
            get_logger().error(f"unable to submit event {event} to redis: {e}")

    async def stop(self):
        await self.stop_event_reader()
        await super().stop()

    async def reset(self):
        await super().reset()
        self.event_handlers = {}  # key = event.name, value = [EventHandler]
