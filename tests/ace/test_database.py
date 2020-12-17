# vim: sw=4:ts=4:et:cc=120

import uuid

import ace
from ace.system.analysis_tracking import track_root_analysis, get_root_analysis
from ace.database import initialize_database, get_db_connection, execute_with_retry

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
def test_get_db_connection():
    with get_db_connection() as db:
        c = db.cursor()
        c.execute("SELECT 1")
        result = c.fetchone()
        assert result[0] == 1

@pytest.mark.integration
def test_sqlalchemy_query():
    result = ace.db.execute("SELECT 1")
    assert result.scalar() == 1

@pytest.mark.integration
def test_execute_with_retry():
    with get_db_connection() as db:
        c = db.cursor()

        # simple single statement transaction
        execute_with_retry(db, c, [ 'SELECT 1' ], [ tuple() ])
        db.commit()

        # multi statement transaction
        execute_with_retry(db, c, [ 
            "INSERT INTO `test` ( `key`, `value` ) VALUES ( ?, ? )",
            'UPDATE `test` SET `value` = ? WHERE `key` = ?',
            'DELETE FROM `test` WHERE `key` = ?',
        ], [ 
            ("key", "value"),
            ("key", "value"),
            ("key",),
        ])
        db.commit()

@pytest.mark.integration
def test_execute_with_retry_commit():

    # simple insert statement with commit option
    with get_db_connection() as db:
        c = db.cursor()
        execute_with_retry(db, c, "INSERT INTO `test` ( `key`, `value` ) VALUES ( ?, ? )", ('key', 'value'), commit=True)

    # check it on another connection
    with get_db_connection() as db:
        c = db.cursor()
        c.execute("SELECT `value` FROM `test` WHERE `key` = ?", ("key",))
        assert c.fetchone()

    # and then this one should fail since we did not commit it
    with get_db_connection() as db:
        c = db.cursor()
        execute_with_retry(db, c, "INSERT INTO `test` ( `key`, `value` ) VALUES ( ?, ? )", ("other", "value"), commit=False)

    with get_db_connection() as db:
        c = db.cursor()
        c.execute("SELECT `value` FROM `test` WHERE `key` = ?", ("other",))
        assert c.fetchone() is None
