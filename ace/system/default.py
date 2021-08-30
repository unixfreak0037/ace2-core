# vim: ts=4:sw=4:et:cc=120
#

from ace.system.database import DatabaseACESystem
from ace.system.redis import RedisACESystem


class DefaultACESystem(RedisACESystem, DatabaseACESystem):
    pass
