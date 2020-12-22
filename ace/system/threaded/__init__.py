# vim: ts=4:sw=4:et:cc=120
#
# threaded implementation of the ACE Engine
# useful for unit testing
#

import threading


class ThreadedInterface:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sync_lock = threading.RLock()
