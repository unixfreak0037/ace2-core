# vim: sw=4:ts=4:et:cc=120

import uuid

import ace
from ace.system.analysis_tracking import track_root_analysis, get_root_analysis
from ace.database import initialize_database

import pytest


@pytest.fixture(autouse=True, scope="function")
def initialize():
    ace.database.initialize_database()

    from ace.database import Base, engine

    Base.metadata.bind = engine
    Base.metadata.create_all()

    ace.db.execute("""CREATE TABLE test ( key TEXT PRIMARY KEY, value TEXT )""")
    ace.db.commit()


@pytest.mark.integration
def test_sqlalchemy_query():
    result = ace.db.execute("SELECT 1")
    assert result.scalar() == 1
