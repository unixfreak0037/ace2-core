# vim: sw=4:ts=4:et:cc=120

import uuid

import ace

from ace.system.database import DatabaseACESystem
from ace.system.database.schema import Config

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import select, insert, text


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.parametrize(
    "sql,params,commit",
    [
        ("INSERT INTO `config` ( `key`, `value` ) VALUES ( :test, :value )", {"test": "test", "value": "value"}, True),
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
                "INSERT INTO `config` ( `key`, `value` ) VALUES ( :test, :value )",
                "INSERT INTO `config` ( `key`, `value` ) VALUES ( :test, :value )",
            ],
            [
                {"test": "test", "value": "value"},
                {"test": "test2", "value": "value2"},
            ],
            True,
        ),
        # (lambda db, cursor: True, (), True),
    ],
)
async def test_execute_with_retry(sql, params, commit, system):
    if not isinstance(system, DatabaseACESystem):
        pytest.skip("database-only test")

    async with system.get_db() as db:
        await system.execute_with_retry(db, sql, params, commit=commit)
        await db.commit()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_execute_with_retry_invalid_length(system):
    if not isinstance(system, DatabaseACESystem):
        pytest.skip("database-only test")

    async with system.get_db() as db:
        with pytest.raises(ValueError):
            await system.execute_with_retry(db, ["SELECT :param_1", "SELECT :param_1"], [{"param_1": 1, "param_2": 2}])


@pytest.mark.asyncio
@pytest.mark.unit
async def test_execute_with_retry_deadlock(system):
    if not isinstance(system, DatabaseACESystem):
        pytest.skip("database-only test")

    async with system.get_db() as db:
        await db.execute(
            text(
                """CREATE TRIGGER trigger_deadlock BEFORE INSERT ON `config` BEGIN 
            SELECT CASE WHEN 1 THEN RAISE ( ROLLBACK, 'DEADLOCK' ) END; END"""
            )
        )
        await db.commit()

    async with system.get_db() as db:
        with pytest.raises(IntegrityError):
            await system.execute_with_retry(
                db,
                "INSERT INTO `config` ( `key`, `value` ) VALUES ( :test, :value )",
                {"test": "test", "value": "value"},
                commit=True,
            )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_retry_on_deadlock_single_executable(system):
    if not isinstance(system, DatabaseACESystem):
        pytest.skip("database-only test")

    await system.retry_on_deadlock(insert(Config).values(key="test", value="value"), commit=True)
    async with system.get_db() as db:
        assert (await db.execute(select(Config).where(Config.key == "test"))).scalar().value == "value"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_retry_on_deadlock_multi_executable(system):
    if not isinstance(system, DatabaseACESystem):
        pytest.skip("database-only test")

    await system.retry_on_deadlock(
        [
            insert(Config).values(key="test", value="value"),
            insert(Config).values(key="test2", value="value2"),
        ],
        commit=True,
    )

    async with system.get_db() as db:
        assert (await db.execute(select(Config).where(Config.key == "test"))).scalar().value == "value"
        assert (await db.execute(select(Config).where(Config.key == "test2"))).scalar().value == "value2"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_retry_on_deadlock_rollback(system):
    if not isinstance(system, DatabaseACESystem):
        pytest.skip("database-only test")

    async with system.get_db() as db:
        await db.execute(
            text(
                """CREATE TRIGGER trigger_deadlock BEFORE INSERT ON `config` BEGIN 
            SELECT CASE WHEN NEW.key = 'test2' THEN RAISE ( ROLLBACK, 'DEADLOCK' ) END; END"""
            )
        )
        await db.commit()

    with pytest.raises(IntegrityError):
        await system.retry_on_deadlock(
            [
                insert(Config).values(key="test", value="value"),
                insert(Config).values(key="test2", value="value2"),
            ],
            commit=True,
        )

    # neither of these should be set since the entire transaction was rolled back
    async with system.get_db() as db:
        assert (await db.execute(select(Config).where(Config.key == "test"))).one_or_none() is None
        assert (await db.execute(select(Config).where(Config.key == "test2"))).one_or_none() is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_retry_function_on_deadlock(system):
    if not isinstance(system, DatabaseACESystem):
        pytest.skip("database-only test")

    def test_function():
        pass

    await system.retry_function_on_deadlock(test_function)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_retry_sql_on_deadlock(system):
    if not isinstance(system, DatabaseACESystem):
        pytest.skip("database-only test")

    await system.retry_sql_on_deadlock(insert(Config).values(key="test", value="value"), commit=True)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_retry_multi_sql_on_deadlock(system):
    if not isinstance(system, DatabaseACESystem):
        pytest.skip("database-only test")

    await system.retry_multi_sql_on_deadlock(
        [
            insert(Config).values(key="test", value="value"),
            insert(Config).values(key="test2", value="value2"),
        ],
        commit=True,
    )


# @pytest.mark.unit
# def test_retry_decorator():
# @retry
# def my_func():
# pass

# my_func()
