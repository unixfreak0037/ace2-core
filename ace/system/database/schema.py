# vim: sw=4:ts=4:et:cc=120

from datetime import datetime, timezone

from ace.system.database import Base

from sqlalchemy import (
    BigInteger,
    BOOLEAN,
    Binary,
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
    Text,
    UniqueConstraint,
    func,
    text,
)

import sqlalchemy.types
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Table


# https://mike.depalatis.net/blog/sqlalchemy-timestamps.html
class TimeStamp(sqlalchemy.types.TypeDecorator):
    impl = sqlalchemy.types.DateTime
    LOCAL_TIMEZONE = datetime.utcnow().astimezone().tzinfo

    def process_bind_param(self, value: datetime, dialect):
        if value is None:
            return None

        if value.tzinfo is None:
            value = value.astimezone(self.LOCAL_TIMEZONE)

        return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return None

        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)

        return value.astimezone(timezone.utc)


class RootAnalysisTracking(Base):

    __tablename__ = "root_analysis_tracking"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
    }

    uuid = Column(String(36), unique=True, primary_key=True)
    version = Column(String(36), unique=False, primary_key=False, index=True)

    json_data = Column(Text, nullable=False)

    insert_date = Column(TimeStamp, nullable=False, index=True, server_default=text("CURRENT_TIMESTAMP"))


class AnalysisDetailsTracking(Base):

    __tablename__ = "analysis_details_tracking"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
    }

    uuid = Column(String(36), unique=True, primary_key=True)

    root_uuid = Column(
        String(36),
        ForeignKey("root_analysis_tracking.uuid", ondelete="CASCADE", onupdate="CASCADE"),
        index=True,
        nullable=False,
    )

    json_data = Column(Text, nullable=False)

    insert_date = Column(TimeStamp, nullable=False, index=True, server_default=text("CURRENT_TIMESTAMP"))


class AnalysisModuleTracking(Base):

    __tablename__ = "analysis_module_tracking"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
    }

    name = Column(String, unique=True, primary_key=True)

    json_data = Column(Text, nullable=False)


analysis_request_links = Table(
    "analysis_request_links",
    Base.metadata,
    Column(
        "source_id",
        String(36),
        ForeignKey("analysis_request_tracking.id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    ),
    Column(
        "dest_id",
        String(36),
        ForeignKey("analysis_request_tracking.id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    ),
)


class AnalysisRequestTracking(Base):

    __tablename__ = "analysis_request_tracking"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
    }

    id = Column(String(36), primary_key=True)

    insert_date = Column(TimeStamp, nullable=False, index=True, server_default=text("CURRENT_TIMESTAMP"))

    expiration_date = Column(TimeStamp, nullable=True, index=True)

    analysis_module_type = Column(String, nullable=True, index=True)

    cache_key = Column(String, nullable=True, index=True)

    root_uuid = Column(String, nullable=False, index=True)

    json_data = Column(Text, nullable=False)

    lock = Column(TimeStamp, nullable=True)

    # https://docs.sqlalchemy.org/en/14/orm/basic_relationships.html#many-to-many
    linked_requests = relationship(
        "AnalysisRequestTracking",
        secondary=analysis_request_links,
        primaryjoin=id == analysis_request_links.c.source_id,
        secondaryjoin=id == analysis_request_links.c.dest_id,
    )


class AnalysisResultCache(Base):

    __tablename__ = "analysis_result_cache"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
    }

    cache_key = Column(String, primary_key=True)

    expiration_date = Column(TimeStamp, nullable=True, index=True)

    analysis_module_type = Column(String, nullable=False, index=True)

    json_data = Column(Text, nullable=False)


class Lock(Base):

    __tablename__ = "locks"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
    }

    id = Column(String, primary_key=True)

    owner = Column(String, nullable=True, index=True)

    acquire_date = Column(TimeStamp, nullable=True, index=True)

    expiration_date = Column(TimeStamp, nullable=True, index=True)

    count = Column(Integer, nullable=False, default=1)


class LockOwnerWaitTarget(Base):

    __tablename__ = "lock_owner_wait_target"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
    }

    owner = Column(String, primary_key=True)

    lock_id = Column(String, nullable=False)


class Config(Base):

    __tablename__ = "config"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
    }

    key = Column(String, primary_key=True)

    value = Column(String, nullable=True)

    documentation = Column(String, nullable=True)


class Storage(Base):

    __tablename__ = "storage"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
    }

    sha256 = Column(String, primary_key=True)

    # content metadata
    name = Column(String, index=True, nullable=False)
    size = Column(Integer, nullable=False)
    location = Column(String, nullable=False)
    insert_date = Column(TimeStamp, nullable=False, index=True, server_default=text("CURRENT_TIMESTAMP"))
    expiration_date = Column(TimeStamp, nullable=True, index=True)
    custom = Column(String, nullable=True)

    roots = relationship("StorageRootTracking", backref="storage")


class StorageRootTracking(Base):

    __tablename__ = "storage_root_tracking"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
    }

    sha256 = Column(String, ForeignKey("storage.sha256", ondelete="CASCADE", onupdate="CASCADE"), primary_key=True)

    root_uuid = Column(
        String, ForeignKey("root_analysis_tracking.uuid", ondelete="CASCADE", onupdate="CASCADE"), primary_key=True
    )
