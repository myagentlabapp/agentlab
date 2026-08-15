"""SQLAlchemy ORM models for agents and leases."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
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
    price_hourly = Column(Float, nullable=False, default=0.0)
    billing_modes = Column(String, nullable=False, default="monthly")
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
    billing_mode = Column(String, nullable=False, default="monthly")


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Integer, nullable=False, default=0)
    email = Column(String, nullable=True, default="")
    enabled = Column(Integer, nullable=False, default=1)
    balance = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Order(Base):
    """支付订单（虎皮椒）"""
    __tablename__ = "orders"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    agent_id = Column(String, nullable=False, default="")
    title = Column(String, nullable=False, default="")
    amount = Column(Float, nullable=False, default=0.0)
    billing_mode = Column(String, nullable=False, default="monthly")
    duration_days = Column(Integer, nullable=False, default=0)
    duration_hours = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    paid_at = Column(DateTime, nullable=True)


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
    action = Column(String, nullable=False, default="")
    agent_id = Column(String, nullable=False, default="")
    status = Column(String, nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
