# vim: sw=4:ts=4:et:cc=120

CONFIG_DB_URL = "/ace/core/sqlalchemy/url"
CONFIG_DB_KWARGS = "/ace/core/sqlalchemy/kwargs"

import functools
import os
import os.path
import random
import sys
import threading
import time
import warnings
import sqlite3

import ace

from ace.system import ACESystem, get_system, get_logger

from sqlalchemy import create_engine, event
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.sql.expression import Executable
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


def get_db() -> scoped_session:
    """Returns the global scoped_session object."""
    return get_system().db


from ace.system.config import get_config
from ace.system.database.analysis_module import DatabaseAnalysisModuleTrackingInterface
from ace.system.database.analysis_request import DatabaseAnalysisRequestTrackingInterface
from ace.system.database.analysis_tracking import DatabaseAnalysisTrackingInterface
from ace.system.database.caching import DatabaseCachingInterface
from ace.system.database.observables import DatabaseObservableInterface


class DatabaseACESystem:
    """A partial ACE core system that uses SQLAlchemy to manage data."""

    # the URL to use to connect to the database (first argument to create_engine)
    db_url: str = None
    # optional args to create_engine
    db_kwargs: dict = {}

    analysis_tracking = DatabaseAnalysisTrackingInterface()
    caching = DatabaseCachingInterface()
    module_tracking = DatabaseAnalysisModuleTrackingInterface()
    observable = DatabaseObservableInterface()
    request_tracking = DatabaseAnalysisRequestTrackingInterface()

    DatabaseSession = None
    db: scoped_session = None
    engine = None

    def initialize(self):
        """Initializes database connections by creating the SQLAlchemy engine and session objects."""

        # see https://github.com/PyMySQL/PyMySQL/issues/644
        # /usr/local/lib/python3.6/dist-packages/pymysql/cursors.py:170: Warning: (1300, "Invalid utf8mb4 character string: '800363'")
        warnings.filterwarnings(action="ignore", message=".*Invalid utf8mb4 character string.*")

        self.db_url = get_config(CONFIG_DB_URL, default=self.db_url)
        self.db_kwargs = get_config(CONFIG_DB_KWARGS, default=self.db_kwargs)
        self.engine = create_engine(self.db_url, **self.db_kwargs)

        @event.listens_for(self.engine, "connect")
        def connect(dbapi_connection, connection_record):
            pid = os.getpid()
            tid = threading.get_ident()
            connection_record.info["pid"] = pid
            connection_record.info["tid"] = tid

            # XXX check for sqlite
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        @event.listens_for(self.engine, "checkout")
        def checkout(dbapi_connection, connection_record, connection_proxy):
            pid = os.getpid()
            if connection_record.info["pid"] != pid:
                connection_record.connection = connection_proxy.connection = None
                message = f"connection record belongs to pid {connection_record.info['pid']} attempting to check out in pid {pid}"
                get_logger().debug(message)
                raise exc.DisconnectionError(message)

            tid = threading.get_ident()
            if connection_record.info["tid"] != tid:
                connection_record.connection = connection_proxy.connection = None
                message = f"connection record belongs to tid {connection_record.info['tid']} attempting to check out in tid {tid}"
                get_logger().debug(message)
                raise exc.DisconnectionError(message)

        self.DatabaseSession = sessionmaker(bind=self.engine)
        self.db = scoped_session(self.DatabaseSession)


def execute_with_retry(db, cursor, sql_or_func, params=(), attempts=3, commit=False):
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

    assert callable(sql_or_func) or isinstance(sql_or_func, str) or isinstance(sql_or_func, list)
    assert (
        params is None
        or isinstance(params, tuple)
        or (isinstance(params, list) and all([isinstance(_, tuple) for _ in params]))
    )

    # if we are executing sql then make sure we have a list of SQL statements and a matching list
    # of tuple parameters
    if not callable(sql_or_func):
        if isinstance(sql_or_func, str):
            sql_or_func = [sql_or_func]

        if isinstance(params, tuple):
            params = [params]
        elif params is None:
            params = [() for _ in sql_or_func]

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
                results.append(sql_or_func(db, cursor, *params))
            else:
                for (_sql, _params) in zip(sql_or_func, params):
                    # if ace.CONFIG['global'].getboolean('log_sql'):
                    # get_logger().debug(f"executing with retry (attempt #{count}) sql {_sql} with paramters {_params}")
                    cursor.execute(_sql, _params)
                    results.append(cursor.rowcount)

            if commit:
                db.commit()

            if len(results) == 1:
                return results[0]

            return results

        except (DBAPIError, sqlite3.IntegrityError) as e:

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
                    db.rollback()
                except Exception as rollback_error:
                    get_logger().error("rollback failed for transaction in deadlock: {}".format(rollback_error))
                    raise e

                count += 1
                time.sleep(random.uniform(0, 1))
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
def retry_on_deadlock(targets, *args, attempts=2, commit=False, **kwargs):
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
        try:
            last_result = None
            for target in targets:
                if isinstance(target, Executable) or isinstance(target, str):
                    get_db().execute(target, *args, **kwargs)
                elif callable(target):
                    last_result = target(*args, **kwargs)

            if commit:
                get_db().commit()

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
                    get_db().rollback()  # rolls back to the begin_nested()
                except Exception as e:
                    get_logger().error(f"unable to roll back transaction: {e}")

                    et, ei, tb = sys.exc_info()
                    raise e.with_traceback(tb)

                # ... and try again
                time.sleep(0.1)  # ... after a bit
                current_attempt += 1
                continue

            # otherwise we propagate the error
            et, ei, tb = sys.exc_info()
            raise e.with_traceback(tb)


def retry_function_on_deadlock(function, *args, **kwargs):
    assert callable(function)
    return retry_on_deadlock(function, *args, **kwargs)


def retry_sql_on_deadlock(executable, *args, **kwargs):
    assert isinstance(executable, Executable)
    return retry_on_deadlock(executable, *args, **kwargs)


def retry_multi_sql_on_deadlock(executables, *args, **kwargs):
    assert isinstance(executables, list)
    assert all([isinstance(_, Executable) for _ in executables])
    return retry_on_deadlock(executables, *args, **kwargs)


def retry(_func, *args, **kwargs):
    """Executes the wrapped function with retry_on_deadlock."""

    @functools.wraps(_func)
    def wrapper(*w_args, **w_kwargs):
        w_kwargs.update(kwargs)
        return retry_function_on_deadlock(_func, *w_args, **w_kwargs)

    return wrapper
