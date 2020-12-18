import ace.database

from ace.system import get_system
from ace.system.database import DatabaseACESystem

import pytest


@pytest.fixture(autouse=True, scope="function")
def initialize():
    if isinstance(get_system(), DatabaseACESystem):
        ace.database.initialize_database()

        from ace.database import Base, engine

        Base.metadata.bind = engine
        Base.metadata.create_all()
