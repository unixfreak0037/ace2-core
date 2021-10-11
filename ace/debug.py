# vim: sw=4:ts=4:et
#

#
# various utility functions and classes for development and debugging
#

from ace.service.base import ACEService


class NullService(ACEService):
    """A service that does nothing but waits to exit."""

    name = "null"
    description = "A service useful for manual testing."

    async def run(self):
        await self.shutdown_event.wait()
