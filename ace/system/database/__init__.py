# vim: sw=4:ts=4:et:cc=120

import asyncio
import functools
import os
import os.path
import random
import sys
import threading
import time
import warnings

from contextlib import asynccontextmanager
from typing import Union

import ace

from ace.system import ACESystem

from ace.logging import get_logger
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm.session import Session, sessionmaker
from sqlalchemy.sql.expression import Executable
from sqlalchemy.ext.declarative import declarative_base

from ace.system.database.analysis_tracking import DatabaseAnalysisTrackingInterface
from ace.system.database.auth import DatabaseAuthenticationInterface
from ace.system.database.caching import DatabaseCachingInterface
from ace.system.database.config import DatabaseConfigurationInterface
from ace.system.database.module_tracking import DatabaseAnalysisModuleTrackingInterface
from ace.system.database.request_tracking import DatabaseAnalysisRequestTrackingInterface
from ace.system.local.storage import LocalStorageInterface


CONFIG_DB_URL = "/ace/core/sqlalchemy/url"
CONFIG_DB_KWARGS = "/ace/core/sqlalchemy/kwargs"


class DatabaseACESystem(
    DatabaseAnalysisTrackingInterface,
    DatabaseAnalysisModuleTrackingInterface,
    DatabaseAnalysisRequestTrackingInterface,
    DatabaseCachingInterface,
    DatabaseConfigurationInterface,
    LocalStorageInterface,
    DatabaseAuthenticationInterface,
    ACESystem,
):
    """A partial ACE core system that uses SQLAlchemy to manage data."""

    # the URL to use to connect to the database (first argument to create_engine)
    db_url: str = None
    # optional args to create_engine
    db_kwargs: dict = {}

    engine = None

    def __init__(self, *args, db_url=None, db_kwargs={}, **kwargs):
        super().__init__(*args, **kwargs)
        self.db_url = db_url
        self.db_kwargs = db_kwargs

    async def create_database(self):
        """Creates the database at the target URL."""
        from ace.system.database.schema import Base

        Base.metadata.bind = self.engine
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def initialize(self):
        """Initializes database connections by creating the SQLAlchemy engine and session objects."""
        # see https://github.com/PyMySQL/PyMySQL/issues/644
        # /usr/local/lib/python3.6/dist-packages/pymysql/cursors.py:170: Warning: (1300, "Invalid utf8mb4 character string: '800363'")
        warnings.filterwarnings(action="ignore", message=".*Invalid utf8mb4 character string.*")

        if not self.db_url:
            self.db_url = await self.get_config_value(CONFIG_DB_URL, env="ACE_DB_URL", default=self.db_url)

        if not self.db_kwargs:
            self.db_kwargs = await self.get_config_value(CONFIG_DB_KWARGS, default=self.db_kwargs)

        print(f"connecting to {self.db_url} with {self.db_kwargs}")
        self.engine = create_async_engine(self.db_url, **self.db_kwargs)
        self.async_session = sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)
        await super().initialize()

    @asynccontextmanager
    async def get_db(self) -> AsyncSession:
        """Returns the a database session."""
        session = None
        if self.engine is None:
            yield None
        else:
            async with self.async_session() as session:
                yield session

    async def execute_with_retry(
        self,
        db: AsyncSession,
        sql_or_func: Union[str, list, callable],
        params: Union[list[dict], dict] = None,
        attempts: int = 3,
        commit: bool = False,
    ):
        """Executes the given SQL or function (and params) against the given cursor with
        re-attempts up to N times (defaults to 2) on deadlock detection.

        NOTE: deadlock detection is supported for MySQL only.

        NOTE: This is for working with raw SQL execution. If you need to
        retry-on-deadlock using SQLAlchemy look at the retry_on_deadlock function
        instead.

        If sql_or_func is a callable then the function will be called as
        sql_or_func(db, cursor, *params).

        example:
        def my_function(db, cursor, param_1):
            cursor.execute("INSERT INTO table ( column ) VALUES ( ? )", (param_1,))

        execute_with_retry(my_function, ("my_value",))

        To execute a single statement, sql is the parameterized SQL statement
        and params is the tuple of parameter values.  params is optional and defaults
        to an empty tuple.

        example:
        execute_with_retry("INSERT INTO table ( column ) VALUES ( ? )", (param_1,))

        To execute multi-statement transactions, sql is a list of parameterized
        SQL statements, and params is a matching list of tuples of parameters.

        example:
        execute_with_retry([
            "INSERT INTO table_1 ( column ) VALUES ( ? )",
            "INSERT INTO table_2 ( column ) VALUES ( ? )",
        ], [
            (param_1,),
            (param_2,),
        ])

        Returns the rowcount for a single statement, or a list of rowcount for multiple statements,
        or the result of the function call."""

        assert isinstance(db, AsyncSession)
        assert callable(sql_or_func) or isinstance(sql_or_func, str) or isinstance(sql_or_func, list)
        assert (
            params is None
            or isinstance(params, dict)
            or (isinstance(params, list) and all([isinstance(_, dict) for _ in params]))
        )

        # if we are executing sql then make sure we have a list of SQL statements and a matching list
        # of tuple parameters
        if not callable(sql_or_func):
            if isinstance(sql_or_func, str):
                sql_or_func = [sql_or_func]

            if isinstance(params, dict):
                params = [params]
            elif params is None:
                params = [{} for _ in sql_or_func]

            if len(sql_or_func) != len(params):
                raise ValueError(
                    "the length of sql statements does not match the length of parameter tuples: {} {}".format(
                        sql_or_func, params
                    )
                )

        count = 1

        while True:
            try:
                results = []
                if callable(sql_or_func):
                    results.append(sql_or_func(db, *params))
                else:
                    for (_sql, _params) in zip(sql_or_func, params):
                        result = await db.execute(_sql, _params)
                        results.append(result.rowcount)

                if commit:
                    await db.commit()

                if len(results) == 1:
                    return results[0]

                return results

            except (DBAPIError, IntegrityError) as e:

                #
                # XXX
                # this is a hack, not sure how to accomplish this in a db-agnostic way
                # need to determine if the exception thrown was thrown because of a deadlock
                # for MySQL it's this
                # see http://stackoverflow.com/questions/25026244/how-to-get-the-mysql-type-of-error-with-pymysql
                # to explain e.args[0]
                # not sure you can even have a deadlock in sqlite since it's not meant to be multi-threaded
                # so we can fake it with the RAISE command in our testing and use the string DEADLOCK
                #

                if (
                    e.args[0] == 1213 or e.args[0] == 1205 or (isinstance(e.args[0], str) and e.args[0] == "DEADLOCK")
                ) and count < attempts:
                    get_logger().warning("deadlock detected -- trying again (attempt #{})".format(count))
                    try:
                        await db.rollback()
                    except Exception as rollback_error:
                        get_logger().error("rollback failed for transaction in deadlock: {}".format(rollback_error))
                        raise e

                    count += 1
                    await asyncio.sleep(random.uniform(0, 1))
                    continue
                else:
                    if not callable(sql_or_func):
                        i = 0
                        for _sql, _params in zip(sql_or_func, params):
                            get_logger().warning(
                                "DEADLOCK STATEMENT #{} SQL {} PARAMS {}".format(
                                    i, _sql, ",".join([str(_) for _ in _params])
                                )
                            )
                            i += 1

                        # TODO log innodb lock status
                        raise e

    # if target is an executable, then *args is to session.execute function
    # if target is a callable, then *args is to the callable function (whatever that is)
    async def retry_on_deadlock(self, targets, *args, attempts=2, commit=False, **kwargs):
        """Executes the given targets, in order. If a deadlock condition is detected, the database session
        is rolled back and the targets are executed in order, again. This can happen up to :param:attempts times
        before the failure is raised as an exception.

        :param targets Can be any of the following
        * A callable.
        * A list of callables.
        * A sqlalchemy.sql.expression.Executable object.
        * A list of sqlalchemy.sql.expression.Executable objects.
        :param int attempts The maximum number of times the operations are tried before passing the exception on.
        :param bool commit If set to True then the ``commit`` function is called on the session object before returning
        from the function. If a deadlock occurs during the commit then further attempts are made.

        In the case where targets are functions, session can be omitted, in which case :meth:ace.system.database.get_db is used to
        acquire a Session to use. When this is the case, the acquired Session object is passed as a keyword parameter
        to the functions.

        In the case where targets are executables, session cannot be omitted. The executables are passed to the
        ``execute`` function of the Session object as if you had called ``session.execute(target)``.

        :return This function returns the last operation in the list of targets."""

        if not isinstance(targets, list):
            targets = [targets]

        current_attempt = 0
        while True:
            async with self.get_db() as db:
                try:
                    last_result = None
                    for target in targets:
                        if isinstance(target, Executable) or isinstance(target, str):
                            await db.execute(target, *args, **kwargs)
                        elif callable(target):
                            last_result = target(*args, **kwargs)

                    if commit:
                        await db.commit()

                    return last_result

                except (DBAPIError, IntegrityError) as e:
                    # catch the deadlock error ids 1213 and 1205
                    # NOTE this is for MySQL only
                    if (
                        e.orig.args[0] == 1213
                        or e.orig.args[0] == 1205
                        or (isinstance(e.orig.args[0], str) and e.orig.args[0] == "DEADLOCK")
                        and current_attempt < attempts
                    ):
                        get_logger().debug(
                            f"DEADLOCK STATEMENT attempt #{current_attempt + 1} SQL {e.statement} PARAMS {e.params}"
                        )

                        try:
                            await db.rollback()  # rolls back to the begin_nested()
                        except Exception as e:
                            get_logger().error(f"unable to roll back transaction: {e}")

                            et, ei, tb = sys.exc_info()
                            raise e.with_traceback(tb)

                        # ... and try again
                        await asyncio.sleep(0.1)  # ... after a bit
                        current_attempt += 1
                        continue

                    # otherwise we propagate the error
                    et, ei, tb = sys.exc_info()
                    raise e.with_traceback(tb)

    async def retry_function_on_deadlock(self, function, *args, **kwargs):
        assert callable(function)
        return await self.retry_on_deadlock(function, *args, **kwargs)

    async def retry_sql_on_deadlock(self, executable, *args, **kwargs):
        assert isinstance(executable, Executable)
        return await self.retry_on_deadlock(executable, *args, **kwargs)

    async def retry_multi_sql_on_deadlock(self, executables, *args, **kwargs):
        assert isinstance(executables, list)
        assert all([isinstance(_, Executable) for _ in executables])
        return await self.retry_on_deadlock(executables, *args, **kwargs)
