# vim: sw=4:ts=4:et:cc=120

from ace.database import Base

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
    TIMESTAMP,
    Text,
    UniqueConstraint,
    func,
    text,
)


class RootAnalysisTracking(Base):

    __tablename__ = "root_analysis_tracking"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
    }

    uuid = Column(String(36), unique=True, primary_key=True)

    json_data = Column(Text, nullable=False)

    insert_date = Column(TIMESTAMP, nullable=False, index=True, server_default=text("CURRENT_TIMESTAMP"))


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

    insert_date = Column(TIMESTAMP, nullable=False, index=True, server_default=text("CURRENT_TIMESTAMP"))


class AnalysisModuleTracking(Base):

    __tablename__ = "analysis_module_tracking"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
    }

    name = Column(String, unique=True, primary_key=True)

    json_data = Column(Text, nullable=False)


class AnalysisRequestTracking(Base):

    __tablename__ = "analysis_request_tracking"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
    }

    id = Column(String(36), primary_key=True)

    insert_date = Column(TIMESTAMP, nullable=False, index=True, server_default=text("CURRENT_TIMESTAMP"))

    expiration_date = Column(TIMESTAMP, nullable=True, index=True)

    analysis_module_type = Column(String, nullable=True, index=True)

    cache_key = Column(String, nullable=True, index=True)

    json_data = Column(Text, nullable=False)


class AnalysisResultCache(Base):

    __tablename__ = "analysis_result_cache"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
    }

    cache_key = Column(String, primary_key=True)

    expiration_date = Column(TIMESTAMP, nullable=True, index=True)

    json_data = Column(Text, nullable=False)


class Lock(Base):

    __tablename__ = "locks"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
    }

    id = Column(String, primary_key=True)

    owner = Column(String, nullable=True, index=True)

    acquire_date = Column(TIMESTAMP, nullable=True, index=True)

    expiration_date = Column(TIMESTAMP, nullable=True, index=True)

    count = Column(Integer, nullable=False, default=1)


class LockOwnerWaitTarget(Base):

    __tablename__ = "lock_owner_wait_target"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
    }

    owner = Column(String, primary_key=True)

    lock_id = Column(String, nullable=False)
