# vim: sw=4:ts=4:et:cc=120

import sqlite3
import uuid

import ace

from ace.system import get_system
from ace.system.database import (
    DatabaseACESystem,
    get_db,
    execute_with_retry,
    retry_on_deadlock,
    retry_function_on_deadlock,
    retry_sql_on_deadlock,
    retry_multi_sql_on_deadlock,
    retry,
)
from ace.system.database.schema import Config

import pytest
import sqlalchemy.exc


@pytest.mark.unit
@pytest.mark.parametrize(
    "sql,params,commit",
    [
        ("INSERT INTO `config` ( `key`, `value` ) VALUES ( ?,? )", ("test", "value"), True),
        ("INSERT INTO `config` ( `key`, `value` ) VALUES ( 'test', 'value' )", None, True),
        (
            [
                "INSERT INTO `config` ( `key`, `value` ) VALUES ( 'test', 'value' )",
                "INSERT INTO `config` ( `key`, `value` ) VALUES ( 'test2', 'value2' )",
            ],
            None,
            True,
        ),
        (
            [
                "INSERT INTO `config` ( `key`, `value` ) VALUES ( ?,? )",
                "INSERT INTO `config` ( `key`, `value` ) VALUES ( ?,? )",
            ],
            [
                ("test", "value"),
                ("test2", "value2"),
            ],
            True,
        ),
        (lambda db, cursor: True, (), True),
    ],
)
def test_execute_with_retry(sql, params, commit):
    if not isinstance(get_system(), DatabaseACESystem):
        return

    connection = get_system().engine.raw_connection()
    cursor = connection.cursor()
    execute_with_retry(connection, cursor, sql, params, commit=commit)
    connection.close()


@pytest.mark.unit
def test_execute_with_retry_invalid_length():
    if not isinstance(get_system(), DatabaseACESystem):
        return

    connection = get_system().engine.raw_connection()
    cursor = connection.cursor()
    with pytest.raises(ValueError):
        execute_with_retry(connection, cursor, ["SELECT ?", "SELECT ?"], [(1, 2)])
    connection.close()


@pytest.mark.unit
def test_execute_with_retry_deadlock():
    if not isinstance(get_system(), DatabaseACESystem):
        return

    connection = get_system().engine.raw_connection()
    cursor = connection.cursor()
    cursor.execute(
        """CREATE TRIGGER trigger_deadlock BEFORE INSERT ON `config` BEGIN 
        SELECT CASE WHEN 1 THEN RAISE ( ROLLBACK, 'DEADLOCK' ) END; END"""
    )
    connection.commit()

    cursor = connection.cursor()
    with pytest.raises(sqlite3.IntegrityError):
        execute_with_retry(
            connection, cursor, "INSERT INTO `config` ( `key`, `value` ) VALUES ( ?,? )", ("test", "value"), commit=True
        )

    connection.close()


@pytest.mark.unit
def test_retry_on_deadlock_single_executable():
    if not isinstance(get_system(), DatabaseACESystem):
        return

    retry_on_deadlock(Config.__table__.insert().values(key="test", value="value"), commit=True)
    with get_db() as db:
        assert db.query(Config).filter(Config.key == "test").one().value == "value"


@pytest.mark.unit
def test_retry_on_deadlock_multi_executable():
    if not isinstance(get_system(), DatabaseACESystem):
        return

    retry_on_deadlock(
        [
            Config.__table__.insert().values(key="test", value="value"),
            Config.__table__.insert().values(key="test2", value="value2"),
        ],
        commit=True,
    )

    with get_db() as db:
        assert db.query(Config).filter(Config.key == "test").one().value == "value"
        assert db.query(Config).filter(Config.key == "test2").one().value == "value2"


@pytest.mark.unit
def test_retry_on_deadlock_rollback():
    if not isinstance(get_system(), DatabaseACESystem):
        return

    connection = get_system().engine.raw_connection()
    cursor = connection.cursor()
    cursor.execute(
        """CREATE TRIGGER trigger_deadlock BEFORE INSERT ON `config` BEGIN 
        SELECT CASE WHEN NEW.key = 'test2' THEN RAISE ( ROLLBACK, 'DEADLOCK' ) END; END"""
    )
    connection.commit()

    with pytest.raises(sqlalchemy.exc.IntegrityError):
        retry_on_deadlock(
            [
                Config.__table__.insert().values(key="test", value="value"),
                Config.__table__.insert().values(key="test2", value="value2"),
            ],
            commit=True,
        )

    # neither of these should be set since the entire transaction was rolled back
    with get_db() as db:
        assert db.query(Config).filter(Config.key == "test").one_or_none() is None
        assert db.query(Config).filter(Config.key == "test2").one_or_none() is None


@pytest.mark.unit
def test_retry_function_on_deadlock():
    def test_function():
        pass

    retry_function_on_deadlock(test_function)


@pytest.mark.unit
def test_retry_sql_on_deadlock():
    if not isinstance(get_system(), DatabaseACESystem):
        return

    retry_sql_on_deadlock(Config.__table__.insert().values(key="test", value="value"), commit=True)


@pytest.mark.unit
def test_retry_multi_sql_on_deadlock():
    if not isinstance(get_system(), DatabaseACESystem):
        return

    retry_multi_sql_on_deadlock(
        [
            Config.__table__.insert().values(key="test", value="value"),
            Config.__table__.insert().values(key="test2", value="value2"),
        ],
        commit=True,
    )


@pytest.mark.unit
def test_retry_decorator():
    @retry
    def my_func():
        pass

    my_func()
