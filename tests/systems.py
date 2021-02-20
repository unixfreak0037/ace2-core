# vim: ts=4:sw=4:et:cc=120
#

#
# utility system definitions for testing
#

import os
import os.path

from ace.system.threaded import ThreadedACESystem
from ace.system.database import DatabaseACESystem
from ace.system.redis import RedisACESystem


class ThreadedACETestSystem(ThreadedACESystem):
    pass


class DatabaseACETestSystem(DatabaseACESystem, ThreadedACESystem):

    # running the tests in memory works as long as the same db connection is
    # always used

    # db_url = "sqlite:///ace.db"
    db_url = "sqlite://"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def reset(self):
        super().reset()

        self.engine = None

        # remove the temporary file we used
        if os.path.exists("ace.db"):
            os.remove("ace.db")

        # re-initialize and create the database
        self.initialize()
        self.create_database()

    def create_database(self):
        from ace.system.database import Base

        Base.metadata.bind = self.engine
        Base.metadata.create_all()

    def stop(self):
        super().stop()

        if os.path.exists("ace.db"):
            os.remove("ace.db")


class RedisACETestSystem(RedisACESystem, DatabaseACETestSystem, ThreadedACESystem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.redis_connection = None

    def initialize(self):
        super().initialize()

        # if os.path.exists("ace.rdb"):
        # os.remove("ace.rdb")

        # only need to do this once
        if self.redis_connection is None:
            import redislite

            self.redis_connection = redislite.StrictRedis("ace.rdb")
            self.alerting.redis_connection = lambda: self.redis_connection
            self.work_queue.redis_connection = lambda: self.redis_connection
            self.events.redis_connection = lambda: self.redis_connection

    def reset(self):
        super().reset()

        # clear everything
        self.redis_connection.flushall()


class DistributedACETestSystem(RedisACETestSystem):

    db_url = "sqlite:///ace.db"
