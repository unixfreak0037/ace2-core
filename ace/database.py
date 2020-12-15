# vim: sw=4:ts=4:et:cc=120

import collections
import datetime
import functools
import logging
import os
import shutil
import sys
import threading
import time
import uuid
import warnings
import random
import re
import json

from contextlib import closing, contextmanager
from typing import Dict, List, Set
from urllib.parse import urlsplit

import ace
import ace.analysis
import ace.constants

from ace.analysis import RootAnalysis, Indicator, IndicatorList
from ace.constants import *
from ace.error import report_exception
from ace.performance import track_execution_time
from ace.util import abs_path, validate_uuid, create_timedelta, find_all_url_domains
from sqlalchemy.orm import aliased

import pytz
import businesstime
import pymysql
import pymysql.err

from businesstime.holidays import Holidays

@contextmanager
def get_db_connection(name='ace'):
    if name is None:
        name = 'ace'

    connection = None
    try:
        connection = get_pool(name).get_connection()
        yield connection
    finally:
        get_pool(name).return_connection(connection)

def use_db(method=None, name=None):
    """Utility decorator to pass an opened database connection and cursor object as keyword
       parameters db and c respectively. Execute is wrapped in a try/catch for database errors.
       Returns None on error and logs error message and stack trace."""

    if method is None:
        return functools.partial(use_db, name=name)

    @functools.wraps(method)
    def wrapper(*args, **kwargs):
        try:
            with get_db_connection(name=name) as db:
                c = db.cursor()
                return method(db=db, c=c, *args, **kwargs)
        except pymysql.err.MySQLError as e:
            logging.error("database error: {}".format(e))
            report_exception()
            et, ei, tb = sys.exc_info()
            raise e.with_traceback(tb)

    return wrapper

def execute_with_retry(db, cursor, sql_or_func, params=(), attempts=3, commit=False):
    """Executes the given SQL or function (and params) against the given cursor with
       re-attempts up to N times (defaults to 2) on deadlock detection.

       If sql_or_func is a callable then the function will be called as 
       sql_or_func(db, cursor, *params).
       
       To execute a single statement, sql is the parameterized SQL statement
       and params is the tuple of parameter values.  params is optional and defaults
       to an empty tuple.
    
       To execute multi-statement transactions, sql is a list of parameterized
       SQL statements, and params is a matching list of tuples of parameters.
       
       Returns the rowcount for a single statement, or a list of rowcount for multiple statements,
       or the result of the function call."""

    assert callable(sql_or_func) or isinstance(sql_or_func, str) or isinstance(sql_or_func, list)
    assert params is None or isinstance(params, tuple) or ( 
        isinstance(params, list) and all([isinstance(_, tuple) for _ in params]) )

    # if we are executing sql then make sure we have a list of SQL statements and a matching list
    # of tuple parameters
    if not callable(sql_or_func):
        if isinstance(sql_or_func, str):
            sql_or_func = [ sql_or_func ]

        if isinstance(params, tuple):
            params = [ params ]
        elif params is None:
            params = [ () for _ in sql_or_func ]

        if len(sql_or_func) != len(params):
            raise ValueError("the length of sql statements does not match the length of parameter tuples: {} {}".format(
                             sql_or_func, params))
    count = 1
    while True:
        try:
            results = []
            if callable(sql_or_func):
                results.append(sql_or_func(db, cursor, *params))
            else:
                for (_sql, _params) in zip(sql_or_func, params):
                    if ace.CONFIG['global'].getboolean('log_sql'):
                        logging.debug(f"executing with retry (attempt #{count}) sql {_sql} with paramters {_params}")
                    cursor.execute(_sql, _params)
                    results.append(cursor.rowcount)

            if commit:
                db.commit()

            if len(results) == 1:
                return results[0]
            
            return results

        except pymysql.err.OperationalError as e:
            # see http://stackoverflow.com/questions/25026244/how-to-get-the-mysql-type-of-error-with-pymysql
            # to explain e.args[0]
            if (e.args[0] == 1213 or e.args[0] == 1205) and count < attempts:
                logging.warning("deadlock detected -- trying again (attempt #{})".format(count))
                try:
                    db.rollback()
                except Exception as rollback_error:
                    logging.error("rollback failed for transaction in deadlock: {}".format(rollback_error))
                    raise e

                count += 1
                time.sleep(random.uniform(0, 1))
                continue
            else:
                if not callable(sql_or_func):
                    i = 0
                    for _sql, _params in zip(sql_or_func, params):
                        logging.warning("DEADLOCK STATEMENT #{} SQL {} PARAMS {}".format(i, _sql, ','.join([str(_) for _ in _params])))
                        i += 1

                    # TODO log innodb lock status
                    raise e

# new school database connections
import logging
import os.path
from sqlalchemy import (
        BigInteger,
        Column,
        DATE,
        DATETIME,
        DateTime,
        Enum,
        ForeignKey,
        Index,
        Integer,
        LargeBinary,
        String,
        TIMESTAMP,
        Text,
        UniqueConstraint,
        create_engine,
        event,
        exc,
        func,
        text,)

# XXX get rid of these
from sqlalchemy.dialects.mysql import BOOLEAN, VARBINARY, BLOB

from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import sessionmaker, relationship, reconstructor, backref, validates, scoped_session
from sqlalchemy.orm.exc import NoResultFound, DetachedInstanceError
from sqlalchemy.sql.expression import Executable
from sqlalchemy.orm.session import Session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import and_, or_
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

DatabaseSession = None
Base = declarative_base()
engine = None

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

       In the case where targets are functions, session can be omitted, in which case :meth:ace.db is used to 
       acquire a Session to use. When this is the case, the acquired Session object is passed as a keyword parameter
       to the functions.

       In the case where targets are executables, session cannot be omitted. The executables are passed to the
       ``execute`` function of the Session object as if you had called ``session.execute(target)``.

       :return This function returns the last operation in the list of targets."""

    if not isinstance(targets, list):
        targets = [ targets ]

    current_attempt = 0
    while True:
        try:
            last_result = None
            for target in targets:
                if isinstance(target, Executable) or isinstance(target, str):
                    ace.db.execute(target, *args, **kwargs)
                elif callable(target):
                    last_result = target(*args, **kwargs)

            if commit:
                ace.db.commit()

            return last_result

        except DBAPIError as e:
            # catch the deadlock error ids 1213 and 1205
            # NOTE this is for MySQL only
            if e.orig.args[0] == 1213 or e.orig.args[0] == 1205 and current_attempt < attempts:
                logging.debug(f"DEADLOCK STATEMENT attempt #{current_attempt + 1} SQL {e.statement} PARAMS {e.params}")

                try:
                    ace.db.rollback() # rolls back to the begin_nested()
                except Exception as e:
                    logging.error(f"unable to roll back transaction: {e}")
                    report_exception()

                    et, ei, tb = sys.exc_info()
                    raise e.with_traceback(tb)

                # ... and try again 
                time.sleep(0.1) # ... after a bit
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

def retry(func, *args, **kwargs):
    """Executes the wrapped function with retry_on_deadlock."""
    @functools.wraps(func)
    def wrapper(*w_args, **w_kwargs):
        w_kwargs.update(kwargs)
        return retry_function_on_deadlock(func, *w_args, **w_kwargs)

    return wrapper

class Config(Base):
    """Holds generic key=value configuration settings."""

    __tablename__ = 'config'
    __table_args__ = { 
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
    }

    key = Column(
        String(512), 
        primary_key=True,
        nullable=False)

    value = Column(
        Text, 
        nullable=False)

class User(UserMixin, Base):

    __tablename__ = 'users'
    __table_args__ = { 
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
    }

    id = Column(
        Integer, 
        primary_key=True,
        autoincrement=True)

    username = Column(
        String(64), 
        unique=True, 
        index=True)

    password_hash = Column(String(128))

    email = Column(
        String(64), 
        unique=True, 
        index=True)

    omniscience = Column(
        BOOLEAN, 
        nullable=False, 
        default=False)

    timezone = Column(
        String(512),
        comment='The timezone this user is in. Dates and times will appear in this timezone in the GUI.')

    display_name = Column(
        String(1024),
        comment='The display name of the user. This may be different than the username. This is used in the GUI.')

    queue = Column(
        String(64),
        nullable=False,
        default='default')

    def __str__(self):
        return self.username

    @property
    def gui_display(self):
        """Returns the textual representation of this user in the GUI.
           If the user has a display_name value set then that is returned.
           Otherwise, the username is returned."""

        if self.display_name is not None:
            return self.display_name

        return self.username

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')
    
    @password.setter
    def password(self, value):
        self.password_hash = generate_password_hash(value)

    def verify_password(self, value):
        return check_password_hash(self.password_hash, value)

Index('ix_users_username_email', User.username, User.email, unique=True)

Owner = aliased(User)
DispositionBy = aliased(User)
RemediatedBy = aliased(User)

class Campaign(Base):

    __tablename__ = 'campaign'
    __table_args__ = { 
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
    }

    id = Column(Integer, nullable=False, primary_key=True)
    name = Column(String(128), nullable=False, index=True)

class CloudphishAnalysisResults(Base):

    __tablename__ = 'cloudphish_analysis_results'
    __table_args__ = { 
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
    }

    sha256_url = Column(
        VARBINARY(32),
        primary_key=True,
        nullable=False,
        comment='The binary SHA2 hash of the URL.')

    http_result_code = Column(
        Integer,
        nullable=True,
        comment='The HTTP result code give by the server when it was fetched (200, 404, 500, etc…)')

    http_message = Column(
        String(256),
        nullable=True,
        comment='The message text that came along with the http_result_code.')

    sha256_content = Column(
        VARBINARY(32),
        nullable=True,
        index=True,
        comment='The binary SHA2 hash of the content that was downloaded for the URL.')

    result = Column(
        Enum('UNKNOWN','ERROR','CLEAR','ALERT','PASS'),
        nullable=False,
        default='UNKNOWN',
        comment='The analysis result of the URL. This is updated by the cloudphish_request_analyzer module.')

    insert_date = Column(
        TIMESTAMP,
        nullable=False,
        index=True,
        server_default=text('CURRENT_TIMESTAMP'),
        comment='When this entry was created.')

    uuid = Column(
        String(36),
        nullable=False,
        comment='The UUID of the analysis. This would also become the UUID of the alert if it ends up becoming one.')

    status = Column(
        Enum('NEW','ANALYZING','ANALYZED'),
        nullable=False,
        default='NEW')

class CloudphishContentMetadata(Base):

    __tablename__ = 'cloudphish_content_metadata'
    __table_args__ = { 
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
    }

    sha256_content = Column(
        VARBINARY(32),
        ForeignKey('cloudphish_analysis_results.sha256_content', 
            ondelete='CASCADE',
            onupdate='CASCADE'),
        primary_key=True,
        nullable=False,
        comment='The binary SHA2 hash of the content that was downloaded from the URL.')

    node = Column(
        String(1024),
        nullable=True,
        comment='The name of the node which stores this binary data. This would match the name columns of the nodes table, however, there is not a database relationship because the nodes can change.')

    name = Column(
        VARBINARY(4096),
        nullable=False,
        comment='The name of the file as it was seen either by content disposition of extrapolated from the URL.\nThis is stored in python’s “unicode_internal” format.')

class CloudphishUrlLookup(Base):

    __tablename__ = 'cloudphish_url_lookup'
    __table_args__ = { 
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
    }

    sha256_url = Column(
        VARBINARY(32),
        ForeignKey('cloudphish_analysis_results.sha256_content', 
            ondelete='CASCADE',
            onupdate='CASCADE'),
        primary_key=True,
        nullable=False,
        comment='The SHA256 value of the URL.')

    last_lookup = Column(
        TIMESTAMP,
        nullable=False,
        index=True,
        server_default=text('CURRENT_TIMESTAMP'),
        comment='The last time this URL was looked up. This is updated every time a query is made to cloudphish for this url. URLs that are not looked up after a period of time are cleared out.')

    url = Column( 
        Text,
        nullable=False,
        comment='The value of the URL.')

class Event(Base):

    __tablename__ = 'events'
    __table_args__ = { 
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
    }

    id = Column(
        Integer, 
        primary_key=True,
        nullable=False,
        autoincrement=True)

    creation_date = Column(
        DATE, 
        nullable=False)

    name = Column(
        String(128), 
        nullable=False)

    type = Column(
        Enum(
            'phish',
            'recon',
            'host compromise',
            'credential compromise',
            'web browsing'), 
        nullable=False)

    vector = Column(
        Enum(
            'corporate email',
            'webmail',
            'usb',
            'website',
            'unknown'), 
        nullable=False)

    risk_level = Column(
        Enum(
            '1',
            '2',
            '3'), 
        nullable=False)

    prevention_tool = Column(
        Enum(
            'response team',
            'ips',
            'fw',
            'proxy',
            'antivirus',
            'email filter',
            'application whitelisting',
            'user'), 
        nullable=False)

    remediation = Column(
        Enum(
            'not remediated',
            'cleaned with antivirus',
            'cleaned manually',
            'reimaged',
            'credentials reset',
            'removed from mailbox',
            'network block',
            'NA'), 
        nullable=False)

    status = Column(
        Enum('OPEN','CLOSED','IGNORE'), 
        nullable=False)

    comment = Column(Text)

    campaign_id = Column(
        Integer, 
        ForeignKey('campaign.id', ondelete='CASCADE', onupdate='CASCADE'), 
        nullable=False)

    event_time = Column(
        DATETIME, 
        nullable=True)

    alert_time = Column(
        DATETIME, 
        nullable=True)

    ownership_time = Column(
        DATETIME, 
        nullable=True)

    disposition_time = Column(
        DATETIME, 
        nullable=True)

    contain_time = Column(
        DATETIME, 
        nullable=True)

    remediation_time = Column(
        DATETIME, 
        nullable=True)


    malware = relationship("ace.database.MalwareMapping", passive_deletes=True, passive_updates=True)
    alert_mappings = relationship("ace.database.EventMapping", passive_deletes=True, passive_updates=True)

    @property
    def json(self):
        return {
            'id': self.id,
            'alerts': self.alerts,
            'campaign': self.campaign.name if self.campaign else None,
            'comment': self.comment,
            'creation_date': str(self.creation_date),
            'event_time': str(self.event_time),
            'alert_time': str(self.alert_time),
            'ownership_time': str(self.ownership_time),
            'disposition_time': str(self.ownership_time),
            'contain_time': str(self.contain_time),
            'remediation_time': str(self.remediation_time),
            'disposition': self.disposition,
            'malware': [{mal.name: [t.type for t in mal.threats]} for mal in self.malware],
            'name': self.name,
            'prevention_tool': self.prevention_tool,
            'remediation': self.remediation,
            'risk_level': self.risk_level,
            'status': self.status,
            'tags': self.sorted_tags,
            'type': self.type,
            'vector': self.vector,
            'wiki': self.wiki
        }

    @property
    def alerts(self):
        uuids = []
        for alert_mapping in self.alert_mappings:
            uuids.append(alert_mapping.alert.uuid)
        return uuids

    @property
    def alert_objects(self) -> List['Alert']:
        alerts = [m.alert for m in self.alert_mappings]
        for alert in alerts:
            alert.load()
        return alerts

    @property
    def malware_names(self):
        names = []
        for mal in self.malware:
            names.append(mal.name)
        return names

    @property
    def commentf(self):
        if self.comment is None:
            return ""
        return self.comment

    @property
    def threats(self):
        threats = {}
        for mal in self.malware:
            for threat in mal.threats:
                threats[threat.type] = True
        return threats.keys()

    @property
    def disposition(self):
        if not self.alert_mappings:
            disposition = ace.constants.DISPOSITION_DELIVERY
        else:
            disposition = None

        for alert_mapping in self.alert_mappings:
            if alert_mapping.alert.disposition is None:
                logging.warning(f"alert {alert_mapping.alert} added to event without disposition {alert_mapping.event_id}")
                continue

            if disposition is None or ace.constants.DISPOSITION_RANK[alert_mapping.alert.disposition] > ace.constants.DISPOSITION_RANK[disposition]:
                disposition = alert_mapping.alert.disposition
        return disposition

    @property
    def disposition_rank(self):
        return ace.constants.DISPOSITION_RANK[self.disposition]

    @property
    def sorted_tags(self):
        tags = {}
        for alert_mapping in self.alert_mappings:
            for tag_mapping in alert_mapping.alert.tag_mappings:
                tags[tag_mapping.tag.name] = tag_mapping.tag
        return sorted([x for x in tags.values()], key=lambda x: (-x.score, x.name.lower()))

    @property
    def wiki(self):
        if ace.CONFIG['mediawiki'].getboolean('enabled'):
            domain = ace.CONFIG['mediawiki']['domain']
            date = self.creation_date.strftime("%Y%m%d").replace(' ', '+')
            name = self.name.replace(' ', '+')
            return "{}display/integral/{}+{}".format(domain, date, name)
        else:
            return None

    @property
    def alert_with_email_and_screenshot(self) -> 'ace.database.Alert':
        return next((a for a in self.alert_objects if a.has_email_analysis and a.has_renderer_screenshot), None)

    @property
    def all_emails(self) -> Set['ace.modules.email.EmailAnalysis']:
        emails = set()

        for alert in self.alert_objects:
            observables = alert.find_observables(lambda o: o.get_analysis(ace.modules.email.EmailAnalysis))
            email_analyses = {o.get_analysis(ace.modules.email.EmailAnalysis) for o in observables}

            # Inject the alert's UUID into the EmailAnalysis so that we maintain a link of alert->email
            for email_analysis in email_analyses:
                email_analysis.alert_uuid = alert.uuid

            emails |= email_analyses

        return emails

    @property
    def all_iocs(self) -> List[Indicator]:
        iocs = IndicatorList()

        for alert in self.alert_objects:
            for analysis in alert.all_analysis:
                for ioc in analysis.iocs:
                    iocs.append(ioc)

        for alert in self.alert_objects:
            for observable_ioc in alert.observable_iocs:
                if observable_ioc not in iocs:
                    iocs.append(observable_ioc)

        if any(a.has_email_analysis for a in self.alert_objects):
            for ioc in iocs:
                ioc.tags += ['phish']

        return sorted(iocs, key=lambda x: (x.type, x.value))

    @property
    def all_url_domain_counts(self) -> Dict[str, int]:
        url_domain_counts = {}

        for alert in self.alert_objects:
            domain_counts = find_all_url_domains(alert)
            for d in domain_counts:
                if d not in url_domain_counts:
                    url_domain_counts[d] = domain_counts[d]
                else:
                    url_domain_counts[d] += domain_counts[d]

        return url_domain_counts

    @property
    def all_urls(self) -> Set[str]:
        urls = set()

        for alert in self.alert_objects:
            observables = alert.find_observables(lambda o: o.type == F_URL)
            urls |= {o.value for o in observables}

        return urls

    @property
    def all_user_analysis(self) -> Set['ace.modules.user.UserAnalysis']:
        user_analysis = set()

        for alert in self.alert_objects:
            observables = alert.find_observables(lambda o: o.get_analysis(ace.modules.user.UserAnalysis))
            user_analysis |= {o.get_analysis(ace.modules.user.UserAnalysis) for o in observables}

        return user_analysis

    @property
    def showable_tags(self) -> Dict[str, list]:
        special_tag_names = [tag for tag in ace.CONFIG['tags'] if ace.CONFIG['tags'][tag] in ['special', 'hidden']]

        results = {}
        for alert in self.alert_objects:
            results[alert.uuid] = []
            for tag in alert.sorted_tags:
                if tag.name not in special_tag_names:
                    results[alert.uuid].append(tag)

        return results

Index('ix_events_creation_date_name', Event.creation_date, Event.name, unique=True)

class EventMapping(Base):

    __tablename__ = 'event_mapping'
    __table_args__ = { 
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
    }

    event_id = Column(
        Integer, 
        ForeignKey('events.id', ondelete='CASCADE', onupdate='CASCADE'), 
        primary_key=True)

    alert_id = Column(
        Integer, 
        ForeignKey('alerts.id', ondelete='CASCADE', onupdate='CASCADE'), 
        primary_key=True,
        index=True)

    alert = relationship('ace.database.Alert', backref='event_mapping')
    event = relationship('ace.database.Event', backref='event_mapping')

class Malware(Base):

    __tablename__ = 'malware'
    __table_args__ = { 
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
    }

    id = Column(
        Integer, 
        primary_key=True)

    name = Column(
        String(128), 
        unique=True, 
        index=True)

    threats = relationship("ace.database.MalwareThreatMapping", passive_deletes=True, passive_updates=True)

class MalwareMapping(Base):

    __tablename__ = 'malware_mapping'
    __table_args__ = { 
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
    }

    event_id = Column(
        Integer, 
        ForeignKey('events.id', ondelete='CASCADE', onupdate='CASCADE'), 
        primary_key=True)

    malware_id = Column(
        Integer, 
        ForeignKey('malware.id', ondelete='CASCADE', onupdate='CASCADE'), 
        primary_key=True,
        index=True)

    malware = relationship("ace.database.Malware")

    @property
    def threats(self):
        return self.malware.threats

    @property
    def name(self):
        return self.malware.name

class MalwareThreatMapping(Base):

    __tablename__ = 'malware_threat_mapping'
    __table_args__ = { 
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
    }

    malware_id = Column(
        Integer,
        ForeignKey('malware.id', ondelete='CASCADE', onupdate='CASCADE'),
        primary_key=True)

    type = Column(
        Enum(
            'UNKNOWN',
            'KEYLOGGER',
            'INFOSTEALER',
            'DOWNLOADER',
            'BOTNET',
            'RAT',
            'RANSOMWARE',
            'ROOTKIT',
            'FRAUD',
            'CUSTOMER_THREAT'),
        nullable=False,
        primary_key=True)

class SiteHolidays(Holidays):
    rules = [
        dict(name="New Year's Day", month=1, day=1),
        #dict(name="Birthday of Martin Luther King, Jr.", month=1, weekday=0, week=3),
        #dict(name="Washington's Birthday", month=2, weekday=0, week=3),
        dict(name="Memorial Day", month=5, weekday=0, week=-1),
        dict(name="Independence Day", month=7, day=4),
        dict(name="Labor Day", month=9, weekday=0, week=1),
        #dict(name="Columbus Day", month=10, weekday=0, week=2),
        #dict(name="Veterans Day", month=11, day=11),
        dict(name="Thanksgiving Day", month=11, weekday=3, week=4),
        dict(name="Day After Thanksgiving Day", month=11, weekday=4, week=4),
        dict(name="Chistmas Eve", month=12, day=24),
        dict(name="Chistmas Day", month=12, day=25),
    ]

    def _day_rule_matches(self, rule, dt):
        """
        Day-of-month-specific US federal holidays that fall on Sat or Sun are
        observed on Fri or Mon respectively. Note that this method considers
        both the actual holiday and the day of observance to be holidays.
        """
        if dt.weekday() == 4:
            sat = dt + datetime.timedelta(days=1)
            if super(SiteHolidays, self)._day_rule_matches(rule, sat):
                return True
        elif dt.weekday() == 0:
            sun = dt - datetime.timedelta(days=1)
            if super(SiteHolidays, self)._day_rule_matches(rule, sun):
                return True
        return super(SiteHolidays, self)._day_rule_matches(rule, dt)


class Alert(RootAnalysis, Base):

    def _initialize(self):
        # Create a businesstime object for SLA with the correct start and end hours converted to UTC
        _bhours = ace.CONFIG['SLA']['business_hours'].split(',')
        self._bh_tz = pytz.timezone(ace.CONFIG['SLA']['time_zone'])
        self._start_hour = int(_bhours[0])
        self._end_hour = int(_bhours[1])
        self._bt = businesstime.BusinessTime(business_hours=(datetime.time(self._start_hour), datetime.time(self._end_hour)), holidays=SiteHolidays())
        # keep track of what Tag and Observable objects we add as we analyze
        self._tracked_tags = [] # of ace.analysis.Tag
        self._tracked_observables = [] # of ace.analysis.Observable
        self._synced_tags = set() # of Tag.name
        self._synced_observables = set() # of '{}:{}'.format(observable.type, observable.value)
        self.add_event_listener(ace.constants.EVENT_GLOBAL_TAG_ADDED, self._handle_tag_added)
        self.add_event_listener(ace.constants.EVENT_GLOBAL_OBSERVABLE_ADDED, self._handle_observable_added)

        # when we lock the Alert this is the UUID we used to lock it with
        self.lock_uuid = str(uuid.uuid4())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._initialize()

    @reconstructor
    def init_on_load(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._initialize()

    def load(self, *args, **kwargs):
        try:
            result = super().load(*args, **kwargs)
        finally:
            # the RootAnalysis object actually loads everything from JSON
            # this may not exactly match what is in the database (it should)
            # the data in the json is the authoritative source
            # see https://ace-ecosystem.github.io/ACE/design/alert_storage/#alert-storage-vs-database-storage
            session = Session.object_session(self)
            if session:
                # so if this alert is attached to a Session, at this point the session becomes dirty
                # because we've loaded all the values from json that we've already loaded from the database
                # so we discard those changes
                session.expire(self)
                # and then reload from the database
                session.refresh(self)
                # XXX inefficient but we'll move to a better design when we're fully containerized

        return result

    #
    # column definitions
    #

    __tablename__ = 'alerts'
    __table_args__ = { 
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
    }

    id = Column(
        Integer, 
        primary_key=True)

    uuid = Column(
        String(36), 
        unique=True, 
        nullable=False)

    insert_date = Column(
        TIMESTAMP, 
        nullable=False, 
        index=True,
        server_default=text('CURRENT_TIMESTAMP'))

    storage_dir = Column(
        String(512), 
        unique=True, 
        nullable=False)

    tool = Column(
        String(256),
        nullable=False)

    tool_instance = Column(
        String(1024),
        nullable=False)

    alert_type = Column(
        String(64),
        nullable=False,
        index=True)

    description = Column(
        String(1024),
        nullable=False)

    priority = Column(
        Integer,
        nullable=False,
        default=0)

    disposition = Column(
        Enum(
            ace.constants.DISPOSITION_FALSE_POSITIVE,
            ace.constants.DISPOSITION_IGNORE,
            ace.constants.DISPOSITION_UNKNOWN,
            ace.constants.DISPOSITION_REVIEWED,
            ace.constants.DISPOSITION_GRAYWARE,
            ace.constants.DISPOSITION_POLICY_VIOLATION,
            ace.constants.DISPOSITION_RECONNAISSANCE,
            ace.constants.DISPOSITION_WEAPONIZATION,
            ace.constants.DISPOSITION_DELIVERY,
            ace.constants.DISPOSITION_EXPLOITATION,
            ace.constants.DISPOSITION_INSTALLATION,
            ace.constants.DISPOSITION_COMMAND_AND_CONTROL,
            ace.constants.DISPOSITION_EXFIL,
            ace.constants.DISPOSITION_DAMAGE,
            ace.constants.DISPOSITION_INSIDER_DATA_CONTROL,
            ace.constants.DISPOSITION_INSIDER_DATA_EXFIL),
        nullable=True,
        index=True)

    disposition_user_id = Column(
        Integer,
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True)

    disposition_time = Column(
        TIMESTAMP, 
        nullable=True)

    owner_id = Column(
        Integer,
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True)

    owner_time = Column(
        TIMESTAMP,
        nullable=True)

    archived = Column(
        BOOLEAN, 
        nullable=False,
        default=False)

    removal_user_id = Column(
        Integer,
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True)

    removal_time = Column(
        TIMESTAMP,
        nullable=True)

    lock_owner = Column(
        String(256), 
        nullable=True)

    lock_id = Column(
        String(36),
        nullable=True)

    lock_transaction_id = Column(
        String(36),
        nullable=True)

    lock_time = Column(
        TIMESTAMP, 
        nullable=True)

    location = Column(
        String(1024),
        unique=False,
        nullable=False,
        index=True)

    detection_count = Column(
        Integer,
        default=0)

    event_time = Column(
        TIMESTAMP,
        nullable=True)

    queue = Column(
        String(64),
        nullable=False,
        default=ace.constants.QUEUE_DEFAULT,
        index=True)

    #
    # relationships
    #

    disposition_user = relationship('ace.database.User', foreign_keys=[disposition_user_id])
    owner = relationship('ace.database.User', foreign_keys=[owner_id])
    remover = relationship('ace.database.User', foreign_keys=[removal_user_id])
    #observable_mapping = relationship('ace.database.ObservableMapping')
    tag_mappings = relationship('ace.database.TagMapping', passive_deletes=True, passive_updates=True)
    #delayed_analysis = relationship('ace.database.DelayedAnalysis')

    def get_observables(self):
        query = ace.db.query(Observable)
        query = query.join(ObservableMapping, Observable.id == ObservableMapping.observable_id)
        query = query.join(Alert, ObservableMapping.alert_id == Alert.id)
        query = query.filter(Alert.uuid == self.uuid)
        query = query.group_by(Observable.id)
        return query.all()

    def get_remediation_targets(self):
        # XXX hack to get around circular import - probably need to merge some modules into one
        from ace.observables import create_observable

        # get observables for this alert
        observables = self.get_observables()

        # get remediation targets for each observable
        targets = {}
        for o in observables:
            observable = create_observable(o.type, o.display_value)
            for target in observable.remediation_targets:
                targets[target.id] = target

        # return sorted list of targets
        targets = list(targets.values())
        targets.sort(key=lambda x: f"{x.type}|{x.value}")
        return targets

    def get_remediation_status(self):
        targets = self.get_remediation_targets()
        remediations = []
        for target in targets:
            if len(target.history) > 0:
                remediations.append(target.history[0])

        if len(remediations) == 0:
            return 'new'

        s = 'success'
        for r in remediations:
            if not r.successful:
                return 'failed'
            if r.status != 'COMPLETED':
                s = 'processing'
        return s

    @property
    def remediation_status(self):
        return self._remediation_status if hasattr(self, '_remediation_status') else self.get_remediation_status()

    @property
    def remediation_targets(self):
        return self._remediation_targets if hasattr(self, '_remediation_targets') else self.get_remediation_targets()

    def _datetime_to_sla_time_zone(self, dt=None):
        """Returns a datetime.datetime object to it's equivalent in the SLA time zone."""
        if dt is not None:
            assert isinstance(dt, datetime.datetime)
        else:
            dt = datetime.datetime.utcnow()
        # convert to the business hour time zone
        dt = dt.astimezone(self._bh_tz)
        # because the businesshour library's math in -> def _build_spanning_datetimes(self, d1, d2) throws
        # an error if datetime.datetime objects are time zone aware, we make the datetime naive again, 
        # however, the replace method trys to be smart and convert the time back to UTC.. so we explicitly
        # make replace keep the hour set to the business time zone hour UGH
        return dt.replace(hour=dt.hour, tzinfo=None)

    @property
    def observable_iocs(self) -> IndicatorList:
        indicators = IndicatorList()

        for ob in self.find_observables(lambda o: o.type == F_EMAIL_ADDRESS):
            indicators.append(Indicator(I_EMAIL_ADDRESS, ob.value))

        for ob in self.find_observables(lambda o: o.type == F_URL):
            indicators.add_url_iocs(ob.value)

        return indicators

    @property
    def all_email_analysis(self) -> List['ace.modules.email.EmailAnalysis']:
        observables = self.find_observables(lambda o: o.get_analysis(ace.modules.email.EmailAnalysis))
        return [o.get_analysis(ace.modules.email.EmailAnalysis) for o in observables]

    @property
    def has_email_analysis(self) -> bool:
        return bool(self.find_observable(lambda o: o.get_analysis(ace.modules.email.EmailAnalysis)))

    @property
    def has_renderer_screenshot(self) -> bool:
        return any(
            o.type == F_FILE and o.is_image and o.value.startswith('renderer_') and o.value.endswith('.png')
            for o in self.all_observables
        )

    @property
    def screenshots(self) -> List[dict]:
        return [
            {'alert_id': self.uuid, 'observable_id': o.id, 'scaled_width': o.scaled_width, 'scaled_height': o.scaled_height}
            for o in self.all_observables
            if (
                    o.type == F_FILE
                    and o.is_image
                    and o.value.startswith('renderer_')
                    and o.value.endswith('.png')
            )
        ]

    @property
    def sla(self):
        """Returns the correct SLA for this alert, or None if SLA is disabled for this alert."""
        if hasattr(self, '_sla_settings'):
            return getattr(self, '_sla_settings')

        target_sla = None

        # find the SLA setting that matches this alert
        try:
            for sla in ace.OTHER_SLA_SETTINGS:
                #logging.info("MARKER: {} {} {}".format(self.uuid, getattr(self, sla._property), sla._value))
                if str(getattr(self, sla._property)) == str(sla._value):
                    logging.debug("alert {} matches property {} value {} for SLA {}".format(
                                   self, sla._property, sla._value, sla.name))
                    target_sla = sla
                    break

            # if nothing matched then just use global sla
            if target_sla is None:
                #logging.debug("alert {} uses global SLA settings".format(self))
                target_sla = ace.GLOBAL_SLA_SETTINGS

        except Exception as e:
            logging.error("unable to get SLA: {}".format(e))

        setattr(self, '_sla_settings', target_sla)
        return target_sla

    @property
    def business_time(self):
        """Returns a time delta that represents how old this alert is in business days and hours."""
        # remember that 1 day == _end_hour - _start_hour (default: 12)
        if hasattr(self, '_business_time'):
            return getattr(self, '_business_time')

        sla_now = self._datetime_to_sla_time_zone()
        _converted_insert_date = self._datetime_to_sla_time_zone(dt=self.insert_date)
        #logging.debug("Getting business time delta between '{}' and '{}' - CONVERTED: '{}' and '{}' - tzino: {} and {}".format(self.insert_date,
                                        #datetime.datetime.now(), _converted_insert_date, self._datetime_to_sla_time_zone(), _converted_insert_date.tzinfo, sla_now.tzinfo))
        result = self._bt.businesstimedelta(_converted_insert_date, self._datetime_to_sla_time_zone())
        #logging.debug("Got business time delta of '{}'".format(result))
        setattr(self, '_business_time', result)
        return result

    @property
    def business_time_str(self):
        """Returns self.business_time as a formatted string for display."""
        result = ""
        if self.business_time.days:
            result = '{} day{}'.format(self.business_time.days, 's' if self.business_time.days > 1 else '')

        hours = int(self.business_time.seconds / 60 / 60)
        if hours:
            result = '{}, {} hour{}'.format(result, int(self.business_time.seconds / 60 / 60), 's' if hours > 1 else '')
        return result

    @property
    def business_time_seconds(self):
        """Returns self.business_time as seconds (computing _end_time -  start_time hours per day.)"""
        hours_per_day = self._end_hour - self._start_hour
        return ((self.business_time.days * hours_per_day * 60 * 60) + 
                (self.business_time.seconds))

    @property
    def is_approaching_sla(self):
        """Returns True if this Alert is approaching SLA and has not been dispositioned yet."""
        if hasattr(self, '_is_approaching_sla'):
            return getattr(self, '_is_approaching_sla')

        if self.insert_date is None:
            return None

        if self.sla is None:
            logging.warning("cannot get SLA for {}".format(self))
            return None

        result = False
        if self.disposition is None and self.sla.enabled and self.alert_type not in ace.EXCLUDED_SLA_ALERT_TYPES:
            result = self.business_time_seconds >= (self.sla.timeout - self.sla.warning) * 60 * 60

        setattr(self, '_is_approaching_sla', result)
        return result

    @property
    def is_over_sla(self):
        """Returns True if this Alert is over SLA and has not been dispositioned yet."""
        if hasattr(self, '_is_over_sla'):
            return getattr(self, '_is_over_sla')

        if self.insert_date is None:
            return None

        if self.sla is None:
            logging.warning("cannot get SLA for {}".format(self))
            return None

        result = False
        if self.disposition is None and self.sla.enabled and self.alert_type not in ace.EXCLUDED_SLA_ALERT_TYPES:
            result = self.business_time_seconds >= self.sla.timeout * 60 * 60

        setattr(self, '_is_over_sla', result)
        return result

    @property
    def icon(self):
        """Returns appropriate icon name by attempting to match on self.description or self.tool."""
        description_tokens = {token.lower() for token in re.split('[ _]', self.description)}
        tool_tokens = {token.lower() for token in self.tool.split(' ')}
        type_tokens = {token.lower() for token in self.alert_type.split(' ')}

        available_favicons = set(ace.CONFIG['gui']['alert_favicons'].split(','))

        result = available_favicons.intersection(description_tokens)
        if not result:
            result = available_favicons.intersection(tool_tokens)
            if not result:
                result = available_favicons.intersection(type_tokens)

        if not result:
            return 'default'
        else:
            return result.pop()


    @validates('description')
    def validate_description(self, key, value):
        max_length = getattr(self.__class__, key).prop.columns[0].type.length
        if value and len(value) > max_length:
            return value[:max_length]
        return value

    def archive(self, *args, **kwargs):
        if self.archived:
            logging.warning(f"called archive() on {self} but already archived")
            return None

        result = super().archive(*args, **kwargs)
        self.archived = True
        return result

    @property
    def sorted_tags(self):
        tags = {}
        for tag_mapping in self.tag_mappings:
            tags[tag_mapping.tag.name] = tag_mapping.tag
        return sorted([x for x in tags.values()], key=lambda x: (-x.score, x.name.lower()))

    # we also save these database properties to the JSON data

    KEY_DATABASE_ID = 'database_id'
    KEY_PRIORITY = 'priority'
    KEY_DISPOSITION = 'disposition'
    KEY_DISPOSITION_USER_ID = 'disposition_user_id'
    KEY_DISPOSITION_TIME = 'disposition_time'
    KEY_OWNER_ID = 'owner_id'
    KEY_OWNER_TIME = 'owner_time'
    KEY_REMOVAL_USER_ID = 'removal_user_id'
    KEY_REMOVAL_TIME = 'removal_time'

    @property
    def json(self):
        result = RootAnalysis.json.fget(self)
        result.update({
            Alert.KEY_DATABASE_ID: self.id,
            Alert.KEY_PRIORITY: self.priority,
            Alert.KEY_DISPOSITION: self.disposition,
            Alert.KEY_DISPOSITION_USER_ID: self.disposition_user_id,
            Alert.KEY_DISPOSITION_TIME: self.disposition_time,
            Alert.KEY_OWNER_ID: self.owner_id,
            Alert.KEY_OWNER_TIME: self.owner_time,
            Alert.KEY_REMOVAL_USER_ID: self.removal_user_id,
            Alert.KEY_REMOVAL_TIME: self.removal_time
        })
        return result

    @json.setter
    def json(self, value):
        assert isinstance(value, dict)
        RootAnalysis.json.fset(self, value)

        if not self.id:
            if Alert.KEY_DATABASE_ID in value:
                self.id = value[Alert.KEY_DATABASE_ID]

        if not self.disposition:
            if Alert.KEY_DISPOSITION in value:
                self.disposition = value[Alert.KEY_DISPOSITION]

        if not self.disposition_user_id:
            if Alert.KEY_DISPOSITION_USER_ID in value:
                self.disposition_user_id = value[Alert.KEY_DISPOSITION_USER_ID]

        if not self.disposition_time:
            if Alert.KEY_DISPOSITION_TIME in value:
                self.disposition_time = value[Alert.KEY_DISPOSITION_TIME]

        if not self.owner_id:
            if Alert.KEY_OWNER_ID in value:
                self.owner_id = value[Alert.KEY_OWNER_ID]

        if not self.owner_time:
            if Alert.KEY_OWNER_TIME in value:
                self.owner_time = value[Alert.KEY_OWNER_TIME]

        if not self.removal_user_id:
            if Alert.KEY_REMOVAL_USER_ID in value:
                self.removal_user_id = value[Alert.KEY_REMOVAL_USER_ID]

        if not self.removal_time:
            if Alert.KEY_REMOVAL_TIME in value:
                self.removal_time = value[Alert.KEY_REMOVAL_TIME]

    def _handle_tag_added(self, source, event_type, *args, **kwargs):
        assert args
        assert isinstance(args[0], ace.analysis.Tag)
        tag = args[0]

        try:
            self.sync_tag_mapping(tag)
        except Exception as e:
            logging.error("sync_tag_mapping failed: {}".format(e))
            report_exception()

    def sync_tag_mapping(self, tag):
        tag_id = None

        with get_db_connection() as db:
            cursor = db.cursor()
            for _ in range(3): # make sure we don't enter an infinite loop here
                cursor.execute("SELECT id FROM tags WHERE name = %s", ( tag.name, ))
                result = cursor.fetchone()
                if result:
                    tag_id = result[0]
                    break
                else:
                    try:
                        execute_with_retry(db, cursor, "INSERT IGNORE INTO tags ( name ) VALUES ( %s )""", ( tag.name, ))
                        db.commit()
                        continue
                    except pymysql.err.InternalError as e:
                        if e.args[0] == 1062:

                            # another process added it just before we did
                            try:
                                db.rollback()
                            except:
                                pass

                            break
                        else:
                            raise e

            if not tag_id:
                logging.error("unable to find tag_id for tag {}".format(tag.name))
                return

            try:
                execute_with_retry(db, cursor, "INSERT IGNORE INTO tag_mapping ( alert_id, tag_id ) VALUES ( %s, %s )", ( self.id, tag_id ))
                db.commit()
                logging.debug("mapped tag {} to {}".format(tag, self))
            except pymysql.err.InternalError as e:
                if e.args[0] == 1062: # already mapped
                    return
                else:
                    raise e

    def _handle_observable_added(self, source, event_type, *args, **kwargs):
        assert args
        assert isinstance(args[0], ace.analysis.Observable)
        observable = args[0]

        try:
            self.sync_observable_mapping(observable)
        except Exception as e:
            logging.error("sync_observable_mapping failed: {}".format(e))
            #report_exception()

    @retry
    def sync_observable_mapping(self, observable):
        assert isinstance(observable, ace.analysis.Observable)

        existing_observable = sync_observable(observable)
        assert existing_observable.id is not None
        ace.db.execute(ObservableMapping.__table__.insert().prefix_with('IGNORE').values(observable_id=existing_observable.id, alert_id=self.id))
        ace.db.commit()

    @retry
    def sync(self):
        """Saves the Alert to disk and database."""
        assert self.storage_dir is not None # requires a valid storage_dir at this point
        assert isinstance(self.storage_dir, str)

        # compute number of detection points
        self.detection_count = len(self.all_detection_points)

        # save the alert to the database
        session = Session.object_session(self)
        if session is None:
            session = ace.db()
        
        session.add(self)
        session.commit()
        self.build_index()

        self.save() # save this alert now that it has the id

        # we want to unlock it here since the corelation is going to want to pick it up as soon as it gets added
        #if self.is_locked():
            #self.unlock()

        return True

    @use_db
    def is_locked(self, db, c):
        """Returns True if this Alert has already been locked."""
        c.execute("""SELECT uuid FROM locks WHERE uuid = %s AND TIMESTAMPDIFF(SECOND, lock_time, NOW()) < %s""", 
                 (self.uuid, ace.LOCK_TIMEOUT_SECONDS))
        row = c.fetchone()
        if row is None:
            return False

        return True

    def reset(self):
        super().reset()

        if self.id:
            # rebuild the index after we reset the Alert
            self.rebuild_index()

    def build_index(self):
        """Rebuilds the data for this Alert in the observables, tags, observable_mapping and tag_mapping tables."""
        self.rebuild_index()

    def rebuild_index(self):
        """Rebuilds the data for this Alert in the observables, tags, observable_mapping and tag_mapping tables."""
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            with get_db_connection() as db:
                c = db.cursor()
                execute_with_retry(db, c, self._rebuild_index)

    def _rebuild_index(self, db, c):
        logging.info(f"rebuilding indexes for {self}")
        c.execute("""DELETE FROM observable_mapping WHERE alert_id = %s""", ( self.id, ))
        c.execute("""DELETE FROM tag_mapping WHERE alert_id = %s""", ( self.id, ))
        c.execute("""DELETE FROM observable_tag_index WHERE alert_id = %s""", ( self.id, ))

        tag_names = tuple([ tag.name for tag in self.all_tags ])
        if tag_names:
            sql = "INSERT IGNORE INTO tags ( name ) VALUES {}".format(','.join(['(%s)' for name in tag_names]))
            #logging.debug(f"MARKER: sql = {sql}")
            c.execute(sql, tag_names)

        all_observables = self.all_observables

        observables = []
        observable_hash_mapping = {} # key = md5, value = observable
        for observable in all_observables:
            observables.append(observable.type)
            observables.append(observable.value)
            observables.append(observable.md5_hex)
            observable_hash_mapping[observable.md5_hex] = observable

        observables = tuple(observables)

        if all_observables:
            sql = "INSERT IGNORE INTO observables ( type, value, md5 ) VALUES {}".format(','.join('(%s, %s, UNHEX(%s))' for o in all_observables))
            #logging.debug(f"MARKER: sql = {sql}")
            c.execute(sql, observables)

        tag_mapping = {} # key = tag_name, value = tag_id
        if tag_names:
            sql = "SELECT id, name FROM tags WHERE name IN ( {} )".format(','.join(['%s' for name in tag_names]))
            #logging.debug(f"MARKER: sql = {sql}")
            c.execute(sql, tag_names)

            for row in c:
                tag_id, tag_name = row
                tag_mapping[tag_name] = tag_id

            sql = "INSERT INTO tag_mapping ( alert_id, tag_id ) VALUES {}".format(','.join(['(%s, %s)' for name in tag_mapping.values()]))
            #logging.debug(f"MARKER: sql = {sql}")
            parameters = []
            for tag_id in tag_mapping.values():
                parameters.append(self.id)
                parameters.append(tag_id)

            c.execute(sql, tuple(parameters))

        observable_mapping = {} # key = observable_id, value = observable
        if all_observables:
            sql = "SELECT id, HEX(md5) FROM observables WHERE md5 IN ( {} )".format(','.join(['UNHEX(%s)' for o in all_observables]))
            #logging.debug(f"MARKER: sql = {sql}")
            c.execute(sql, tuple([o.md5_hex for o in all_observables]))

            for row in c:
                observable_id, md5_hex = row
                observable_mapping[md5_hex.lower()] = observable_id

            sql = "INSERT INTO observable_mapping ( alert_id, observable_id ) VALUES {}".format(','.join(['(%s, %s)' for o in observable_mapping.keys()]))
            #logging.debug(f"MARKER: sql = {sql}")
            parameters = []
            for observable_id in observable_mapping.values():
                parameters.append(self.id)
                parameters.append(observable_id)

            c.execute(sql, tuple(parameters))

        sql = "INSERT IGNORE INTO observable_tag_index ( alert_id, observable_id, tag_id ) VALUES "
        parameters = []
        sql_clause = []

        for observable in all_observables:
            for tag in observable.tags:
                try:
                    tag_id = tag_mapping[tag.name]
                except KeyError:
                    logging.debug(f"missing tag mapping for tag {tag.name} in observable {observable} alert {self.uuid}")
                    continue

                observable_id = observable_mapping[observable.md5_hex.lower()]

                parameters.append(self.id)
                parameters.append(observable_id)
                parameters.append(tag_id)
                sql_clause.append('(%s, %s, %s)')

        if sql_clause:
            sql += ','.join(sql_clause)
            #logging.debug(f"MARKER: sql = {sql}")
            c.execute(sql, tuple(parameters))

        db.commit()

    # NOTE there is no database relationship between these tables
    workload = relationship('ace.database.Workload', foreign_keys=[uuid],
                            primaryjoin='ace.database.Workload.uuid == Alert.uuid')

    delayed_analysis = relationship('ace.database.DelayedAnalysis', foreign_keys=[uuid],
                                    primaryjoin='ace.database.DelayedAnalysis.uuid == Alert.uuid')

    lock = relationship('ace.database.Lock', foreign_keys=[uuid],
                        primaryjoin='ace.database.Lock.uuid == Alert.uuid')

    nodes = relationship('ace.database.Nodes', foreign_keys=[location], primaryjoin='ace.database.Nodes.name == Alert.location')

    @property
    def node_location(self):
        return self.nodes.location

@retry
def sync_observable(observable):
    """Syncs the given observable to the database by inserting a row in the observables table if it does not currently exist.
       Returns the existing or newly created ace.database.Observable entry for the corresponding row."""
    existing_observable = ace.db.query(ace.database.Observable).filter(ace.database.Observable.type == observable.type, 
                                                                       ace.database.Observable.md5 == func.UNHEX(observable.md5_hex)).first()
    if existing_observable is None:
        # XXX assuming all observables are encodable in utf-8 is probably wrong
        # XXX we could have some kind of binary data, or an intentionally corrupt value
        # XXX in which case we'd lose the actual value of the data here
        existing_observable = Observable(type=observable.type, 
                                         value=observable.value.encode('utf8', errors='ignore'), 
                                         md5=func.UNHEX(observable.md5_hex))
        ace.db.add(existing_observable)
        ace.db.flush()

    return existing_observable

def set_dispositions(alert_uuids, disposition, user_id, user_comment=None):
    """Utility function to the set disposition of many Alerts at once.
       :param alert_uuids: A list of UUIDs of Alert objects to set.
       :param disposition: The disposition to set the Alerts.
       :param user_id: The id of the User that is setting the disposition.
       :param user_comment: Optional comment the User is providing as part of the disposition."""

    with get_db_connection() as db:
        c = db.cursor()
        # update dispositions
        uuid_placeholders = ','.join(['%s' for _ in alert_uuids])
        sql = f"""UPDATE alerts SET 
                      disposition = %s, disposition_user_id = %s, disposition_time = NOW(),
                      owner_id = %s, owner_time = NOW()
                  WHERE 
                      (disposition IS NULL OR disposition != %s) AND uuid IN ( {uuid_placeholders} )"""
        parameters = [disposition, user_id, user_id, disposition]
        parameters.extend(alert_uuids)
        c.execute(sql, parameters)
        
        # add the comment if it exists
        if user_comment:
            for uuid in alert_uuids:
                c.execute("""
                          INSERT INTO comments ( user_id, uuid, comment ) 
                          VALUES ( %s, %s, %s )""", ( user_id, uuid, user_comment))

class Similarity:
    def __init__(self, uuid, disposition, percent):
        self.uuid = uuid
        self.disposition = disposition
        self.percent = round(float(percent))

class UserAlertMetrics(Base):
    
    __tablename__ = 'user_alert_metrics'

    alert_id = Column(
        Integer,
        ForeignKey('alerts.id'),
        primary_key=True)

    user_id = Column(
        Integer,
        ForeignKey('users.id'),
        primary_key=True)

    start_time = Column(
        TIMESTAMP, 
        nullable=False, 
        server_default=text('CURRENT_TIMESTAMP'))

    disposition_time = Column(
        TIMESTAMP, 
        nullable=True)

    alert = relationship('ace.database.Alert', backref='user_alert_metrics')
    user = relationship('User', backref='user_alert_metrics')

class Comment(Base):

    __tablename__ = 'comments'
    __table_args__ = { 
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
    }

    comment_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True)

    insert_date = Column(
        TIMESTAMP, 
        nullable=False, 
        index=True,
        server_default=text('CURRENT_TIMESTAMP'))

    user_id = Column(
        Integer,
        ForeignKey('users.id'),
        nullable=False,
        index=True)

    uuid = Column(
        String(36), 
        ForeignKey('alerts.uuid', ondelete='CASCADE'),
        nullable=False,
        index=True)

    comment = Column(
        Text,
        nullable=False)

    # many to one
    user = relationship('User', backref='comments')
    # TODO add other relationships?

class Observable(Base):

    __tablename__ = 'observables'
    __table_args__ = { 
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
    }

    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True)

    type = Column(
        String(64),
        nullable=False)

    value = Column(
        BLOB,
        nullable=False)

    md5 = Column(
        VARBINARY(16),
        nullable=False,
        index=True)

    @property
    def display_value(self):
        return self.value.decode('utf8', errors='ignore')

    tags = relationship('ace.database.ObservableTagMapping', passive_deletes=True, passive_updates=True)

Index('ix_observable_type_md5', Observable.type, Observable.md5, unique=True)

class ObservableMapping(Base):

    __tablename__ = 'observable_mapping'
    __table_args__ = { 
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
    }

    observable_id = Column(
        Integer,
        ForeignKey('observables.id', ondelete='CASCADE', onupdate='CASCADE'),
        primary_key=True)

    alert_id = Column(
        Integer,
        ForeignKey('alerts.id', ondelete='CASCADE', onupdate='CASCADE'),
        primary_key=True,
        index=True)

    alert = relationship('ace.database.Alert', backref='observable_mappings')
    observable = relationship('ace.database.Observable', backref='observable_mappings')

# this is used to automatically map tags to observables
# same as the etc/site_tags.csv really, just in the database
class ObservableTagMapping(Base):
    
    __tablename__ = 'observable_tag_mapping'
    __table_args__ = { 
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
    }

    observable_id = Column(
        Integer,
        ForeignKey('observables.id', ondelete='CASCADE', onupdate='CASCADE'),
        primary_key=True,
        index=True)

    tag_id = Column(
        Integer,
        ForeignKey('tags.id', ondelete='CASCADE', onupdate='CASCADE'),
        primary_key=True)

    observable = relationship('ace.database.Observable', backref='observable_tag_mapping')
    tag = relationship('ace.database.Tag', backref='observable_tag_mapping')

def add_observable_tag_mapping(o_type, o_value, o_md5, tag):
    """Adds the given observable tag mapping specified by type, and md5 (hex string) and the tag you want to map.
       If the observable does not exist and o_value is provided then the observable is added to the database.
       Returns True if the mapping was successful, False otherwise."""

    try:
        tag = ace.db.query(ace.database.Tag).filter(ace.database.Tag.name == tag).one()
    except NoResultFound as e:
        ace.db.execute(ace.database.Tag.__table__.insert().values(name=tag))
        ace.db.commit()
        tag = ace.db.query(ace.database.Tag).filter(ace.database.Tag.name == tag).one()

    observable = None

    if o_md5 is not None:
        try:
            observable = ace.db.query(ace.database.Observable).filter(ace.database.Observable.type==o_type, 
                                                                      ace.database.Observable.md5==func.UNHEX(o_md5)).one()
        except NoResultFound as e:
            if o_value is None:
                logging.warning(f"observable type {o_type} md5 {o_md5} cannot be found for mapping")
                return False

    if observable is None:
        from ace.observables import create_observable
        observable = sync_observable(create_observable(o_type, o_value))
        ace.db.commit()

    try:
        mapping = ace.db.query(ObservableTagMapping).filter(ObservableTagMapping.observable_id == observable.id,
                                                            ObservableTagMapping.tag_id == tag.id).one()
        ace.db.commit()
        return True

    except NoResultFound as e:
        ace.db.execute(ObservableTagMapping.__table__.insert().values(observable_id=observable.id, tag_id=tag.id))
        ace.db.commit()
        return True

def remove_observable_tag_mapping(o_type, o_value, o_md5, tag):
    """Removes the given observable tag mapping specified by type, and md5 (hex string) and the tag you want to remove.
       Returns True if the removal was successful, False otherwise."""

    tag = ace.db.query(ace.database.Tag).filter(ace.database.Tag.name == tag).first()
    if tag is None:
        return False

    observable = None
    if o_md5 is not None:
        observable = ace.db.query(ace.database.Observable).filter(ace.database.Observable.type == o_type,
                                                                  ace.database.Observable.md5 == func.UNHEX(o_md5)).first()
    
    if observable is None:
        if o_value is None:
            return False

        from ace.observables import create_observable
        o = create_observable(o_type, o_value)
        observable = ace.db.query(ace.database.Observable).filter(ace.database.Observable.type == o.type,
                                                                  ace.database.Observable.md5 == func.UNHEX(o.md5_hex)).first()

    if observable is None:
        return False

    ace.db.execute(ObservableTagMapping.__table__.delete().where(and_(ObservableTagMapping.observable_id == observable.id,
                                                                 ObservableTagMapping.tag_id == tag.id)))
    ace.db.commit()
    return True

class PersistenceSource(Base):

    __tablename__ = 'persistence_source'
    __table_args__ = { 
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
    }
    
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True)

    name = Column(
        String(256),
        nullable=False,
        index=True,
        comment='The name of the persistence source. For example, the name of the ace collector.')

class Persistence(Base):

    __tablename__ = 'persistence'
    __table_args__ = { 
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
    }

    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True)

    source_id = Column(
        Integer,
        ForeignKey('persistence_source.id', ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False,
        comment='The source that generated this persistence data.'
    )

    permanent = Column(
        BOOLEAN,
        nullable=False,
        default=False,
        comment='Set to 1 if this value should never be deleted, 0 otherwise.')

    uuid = Column(
        String(512),
        nullable=False,
        comment='A unique identifier (key) for this piece of persistence data specific to this source.')

    value = Column(
        LargeBinary,
        nullable=True,
        comment='The value of this piece of persistence data. This is pickled python data.')

    created_at = Column(
        TIMESTAMP, 
        nullable=False, 
        index=True,
        server_default=text('CURRENT_TIMESTAMP'),
        comment='The time this information was created.')

    last_update = Column(
        TIMESTAMP, 
        nullable=False, 
        index=True,
        server_default=text('CURRENT_TIMESTAMP'),
        comment='The last time this information was updated.')

Index('ix_persistence_source_id_uuid', Persistence.source_id, Persistence.uuid, unique=True)
Index('ix_persistence_permanent_last_update', Persistence.permanent, Persistence.last_update)

# this is used to map what observables had what tags in what alerts
# not to be confused with ObservableTagMapping (see above)
# I think this is what I had in mind when I originally created ObservableTagMapping
# but I was missing the alert_id field
# that table was later repurposed to automatically map tags to observables

class ObservableTagIndex(Base):

    __tablename__ = 'observable_tag_index'
    __table_args__ = { 
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
    }

    observable_id = Column(
        Integer,
        ForeignKey('observables.id', ondelete='CASCADE', onupdate='CASCADE'),
        primary_key=True)

    tag_id = Column(
        Integer,
        ForeignKey('tags.id', ondelete='CASCADE', onupdate='CASCADE'),
        primary_key=True,
        index=True)

    alert_id = Column(
        Integer,
        ForeignKey('alerts.id', ondelete='CASCADE', onupdate='CASCADE'),
        primary_key=True,
        index=True)

    observable = relationship('ace.database.Observable', backref='observable_tag_index')
    tag = relationship('ace.database.Tag', backref='observable_tag_index')
    alert = relationship('ace.database.Alert', backref='observable_tag_index')

class Tag(Base):
    
    __tablename__ = 'tags'
    __table_args__ = { 
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
    }

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True)

    name = Column(
        String(256),
        nullable=False,
        index=True,
        unique=True)

    @property
    def display(self):
        tag_name = self.name.split(':')[0]
        if tag_name in ace.CONFIG['tags'] and ace.CONFIG['tags'][tag_name] == "special":
            return False
        return True

    @property
    def style(self):
        tag_name = self.name.split(':')[0]
        if tag_name in ace.CONFIG['tags']:
            return ace.CONFIG['tag_css_class'][ace.CONFIG['tags'][tag_name]]
        else:
            return 'label-default'

    #def __init__(self, *args, **kwargs):
        #super(ace.database.Tag, self).__init__(*args, **kwargs)

    @reconstructor
    def init_on_load(self, *args, **kwargs):
        super(ace.database.Tag, self).__init__(*args, **kwargs)

class TagMapping(Base):

    __tablename__ = 'tag_mapping'
    __table_args__ = { 
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
    }

    tag_id = Column(
        Integer,
        ForeignKey('tags.id', ondelete='CASCADE', onupdate='CASCADE'),
        primary_key=True)

    alert_id = Column(
        Integer,
        ForeignKey('alerts.id', ondelete='CASCADE', onupdate='CASCADE'),
        primary_key=True,
        index=True)

    alert = relationship('ace.database.Alert', backref='tag_mapping')
    tag = relationship('ace.database.Tag', backref='tag_mapping')

class Remediation(Base):

    __tablename__ = 'remediation'
    __table_args__ = { 
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
    }

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True)

    type = Column(
        String,
        nullable=False,
        default='email')

    action = Column(
        Enum('remove', 'restore'),
        nullable=False,
        default='remove',
        comment='The action that was taken, either the time was removed or it was restored.')

    insert_date = Column(
        TIMESTAMP, 
        nullable=False, 
        index=True,
        server_default=text('CURRENT_TIMESTAMP'),
        comment='The time the action occured.')

    update_time = Column(
        TIMESTAMP, 
        nullable=True, 
        index=True,
        server_default=None,
        comment='Time the action was last attempted')

    user_id = Column(
        Integer,
        ForeignKey('users.id'),
        nullable=False,
        index=True,
        comment='The user who performed the action.')

    user = relationship('ace.database.User', backref='remediations')

    key = Column(
        String(512),
        nullable=False,
        index=True,
        comment='The key to look up the item.  In the case of emails this is the message_id and the recipient email address.')

    restore_key = Column(
        String(512),
        nullable=True,
        comment='optional location used to restore the file from')

    result = Column(
        Text,
        nullable=True,
        comment='The result of the action.  This is free form data for the analyst to see, usually includes error codes and messages.')

    _results = None

    @property
    def results(self):
        if self._results is None:
            try:
                if self.result is None:
                    self._results = {}
                else:
                    self._results = json.loads(self.result)
            except:
                self._results = {'remediator_deprecated': {'complete': True, 'success':self.successful, 'result':self.result}}
        return self._results

    comment = Column(
        Text,
        nullable=True,
        comment='Optional comment, additional free form data.')
    
    @property
    def alert_uuids(self):
        """If the comment is a comma separated list of alert uuids, then that list is provided here as a property.
           Otherwise this returns an emtpy list."""
        result = []
        if self.comment is None:
            return result

        for _uuid in self.comment.split(','):
            try:
                validate_uuid(_uuid)
                result.append(_uuid)
            except ValueError:
                continue

        return result

    successful = Column(
        BOOLEAN,
        nullable=True,
        default=None,
        comment='1 - remediation worked, 0 - remediation didn’t work')

    lock = Column(
        String(36), 
        nullable=True,
        comment='Set to a UUID when an engine processes it. Defaults to NULL to indicate nothing is working on it.')

    lock_time = Column(
        DateTime,
        nullable=True)

    status = Column(
        Enum('NEW', 'IN_PROGRESS', 'COMPLETED'),
        nullable=False,
        default='NEW',
        comment="""
        The current status of the remediation.
        NEW - needs to be processed
        IN_PROGRESS - entry is currently being processed
        COMPLETED - entry completed successfully""")

    @property
    def json(self):
        return {
            'id': self.id,
            'type': self.type,
            'action': self.action,
            'insert_date': self.insert_date,
            'user_id': self.user_id,
            'key': self.key,
            'result': self.result,
            'comment': self.comment,
            'successful': self.successful,
            'status': self.status,
        }

    def __str__(self):
        return f"Remediation: {self.action} - {self.type} - {self.status} - {self.key} - {self.result}"

class Lock(Base):
    
    __tablename__ = 'locks'
    __table_args__ = { 
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
    }

    uuid = Column(
        String(36),
        primary_key=True,
        nullable=False)

    lock_uuid = Column(
        String(36),
        nullable=False,
        index=True)
    
    lock_time = Column(
        DateTime, 
        nullable=False, 
        index=True)

    lock_owner = Column(
        String(512),
        nullable=True)

Index('ix_locks_uuid_lock_uuid', Lock.uuid, Lock.lock_uuid)

@use_db
def acquire_lock(_uuid, lock_uuid=None, lock_owner=None, db=None, c=None):
    """Attempts to acquire a lock on a workitem by inserting the uuid into the locks database table.
       Returns False if a lock already exists or the lock_uuid if the lock was acquired.
       If a lock_uuid is not given, then a random one is generated and used and returned on success."""

    try:
        if lock_uuid is None:
            lock_uuid = str(uuid.uuid4())

        execute_with_retry(db, c, "INSERT INTO locks ( uuid, lock_uuid, lock_owner, lock_time ) VALUES ( %s, %s, %s, NOW() )", 
                          ( _uuid, lock_uuid, lock_owner ), commit=True)

        logging.debug("locked {} with {}".format(_uuid, lock_uuid))
        return lock_uuid

    except pymysql.err.IntegrityError as e:
        # if a lock already exists -- make sure it's owned by someone else
        try:
            db.rollback()
            # assume we already own the lock -- this will be true in subsequent calls
            # to acquire the lock
            execute_with_retry(db, c, """
UPDATE locks 
SET 
    lock_time = NOW(),
    lock_uuid = %s,
    lock_owner = %s
WHERE 
    uuid = %s 
    AND ( lock_uuid = %s OR TIMESTAMPDIFF(SECOND, lock_time, NOW()) >= %s )
""", (lock_uuid, lock_owner, _uuid, lock_uuid, ace.LOCK_TIMEOUT_SECONDS))
            db.commit()

            c.execute("SELECT lock_uuid, lock_owner FROM locks WHERE uuid = %s", (_uuid,))
            row = c.fetchone()
            if row:
                current_lock_uuid, current_lock_owner = row
                if current_lock_uuid == lock_uuid:
                    logging.debug("locked {} with {}".format(_uuid, lock_uuid))
                    return lock_uuid

                # lock was acquired by someone else
                logging.debug("attempt to acquire lock {} failed (already locked by {}: {})".format(
                             _uuid, current_lock_uuid, current_lock_owner))

            else:
                # lock was acquired by someone else
                logging.info("attempt to acquire lock {} failed".format(_uuid))

            return False

        except Exception as e:
            logging.error("attempt to acquire lock failed: {}".format(e))
            report_exception()
            return False

    except Exception as e:
        logging.error("attempt to acquire lock failed: {}".format(e))
        report_exception()
        return False

@use_db
def release_lock(uuid, lock_uuid, db, c):
    """Releases a lock acquired by acquire_lock."""
    try:
        execute_with_retry(db, c, "DELETE FROM locks WHERE uuid = %s AND lock_uuid = %s", (uuid, lock_uuid,))
        db.commit()
        if c.rowcount == 1:
            logging.debug("released lock on {}".format(uuid))
        else:
            logging.warning("failed to release lock on {} with lock uuid {}".format(uuid, lock_uuid))

        return c.rowcount == 1
    except Exception as e:
        logging.error("unable to release lock {}: {}".format(uuid, e))
        report_exception()

    return False

@use_db
def force_release_lock(uuid, db, c):
    """Releases a lock acquired by acquire_lock without providing the lock_uuid."""
    try:
        execute_with_retry(db, c, "DELETE FROM locks WHERE uuid = %s", (uuid,))
        db.commit()
        if c.rowcount == 1:
            logging.debug("released lock on {}".format(uuid))
        else:
            logging.info("failed to force release lock on {}".format(uuid))

        return c.rowcount == 1
    except Exception as e:
        logging.error("unable to force release lock {}: {}".format(uuid, e))
        report_exception()

    return False

@use_db
def clear_expired_locks(db, c):
    """Clear any locks that have exceeded ace.LOCK_TIMEOUT_SECONDS."""
    execute_with_retry(db, c, "DELETE FROM locks WHERE TIMESTAMPDIFF(SECOND, lock_time, NOW()) >= %s",
                              (ace.LOCK_TIMEOUT_SECONDS,))
    db.commit()
    if c.rowcount:
        logging.debug("removed {} expired locks".format(c.rowcount))

class LockedException(Exception):
    def __init__(self, target, *args, **kwargs):
        self.target = target

    def __str__(self):
        return f"LockedException: unable to get lock on {self.target} uuid {self.target.uuid}"

class EncryptedPasswords(Base):

    __tablename__ = 'encrypted_passwords'
    __table_args__ = { 
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
    }

    key = Column(
        String(256),
        primary_key=True,
        nullable=False,
        comment='The name (key) of the value being stored. Can either be a single name, or a section.option key.')

    encrypted_value = Column(
        Text,
        nullable=False,
        comment='Encrypted value, base64 encoded')
    
def initialize_database():
    """Initializes database connections by creating the SQLAlchemy engine and session objects."""

    global DatabaseSession, engine
    from config import config, get_sqlalchemy_database_uri, get_sqlalchemy_database_options

    # see https://github.com/PyMySQL/PyMySQL/issues/644
    # /usr/local/lib/python3.6/dist-packages/pymysql/cursors.py:170: Warning: (1300, "Invalid utf8mb4 character string: '800363'")
    warnings.filterwarnings(action='ignore', message='.*Invalid utf8mb4 character string.*')

    import ace
    engine = create_engine(
        get_sqlalchemy_database_uri('ace'),
        **get_sqlalchemy_database_options('ace'))

    @event.listens_for(engine, 'connect')
    def connect(dbapi_connection, connection_record):
        pid = os.getpid()
        connection_record.info['pid'] = pid

    @event.listens_for(engine, 'checkout')
    def checkout(dbapi_connection, connection_record, connection_proxy):
        pid = os.getpid()
        if connection_record.info['pid'] != pid:
            connection_record.connection = connection_proxy.connection = None
            message = f"connection record belongs to pid {connection_record.info['pid']} attempting to check out in pid {pid}"
            logging.debug(message)
            raise exc.DisconnectionError(message)

    DatabaseSession = sessionmaker(bind=engine)
    ace.db = scoped_session(DatabaseSession)

def initialize_automation_user():
    # get the id of the ace automation account
    try:
        #import pymysql
        #pymysql.connections.DEBUG = True
        ace.AUTOMATION_USER_ID = ace.db.query(User).filter(User.username == 'ace').one().id
        ace.db.remove()
    except Exception as e:
        # if the account is missing go ahead and create it
        user = User(username='ace', email='ace@localhost', display_name='automation')
        ace.db.add(user)
        ace.db.commit()

        try:
            ace.AUTOMATION_USER_ID = ace.db.query(User).filter(User.username == 'ace').one().id
        except Exception as e:
            logging.critical(f"missing automation account and unable to create it: {e}")
            sys.exit(1)
        finally:
            ace.db.remove()

    logging.debug(f"got id {ace.AUTOMATION_USER_ID} for automation user account")
