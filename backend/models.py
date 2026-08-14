"""SQLAlchemy ORM models for agents and leases."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Agent(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=False, default="")
    icon = Column(String, nullable=False, default="")
    image = Column(String, nullable=False)
    price_monthly = Column(Integer, nullable=False, default=0)
    enabled = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Lease(Base):
    __tablename__ = "leases"

    id = Column(String, primary_key=True)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    user_id = Column(String, nullable=False)
    api_key = Column(String, nullable=False)
    port = Column(Integer, nullable=False)
    container_id = Column(String, nullable=False, default="")
    status = Column(String, nullable=False, default="running")
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    access_password = Column(String, nullable=False, default="")


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Integer, nullable=False, default=0)
    enabled = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False, default="")
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

class ApiLog(Base):
    """API 请求日志（监控用）"""
    __tablename__ = "api_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, default="")
    action = Column(String, nullable=False, default="")   # deploy/stop/list...
    agent_id = Column(String, nullable=False, default="")
    status = Column(String, nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
