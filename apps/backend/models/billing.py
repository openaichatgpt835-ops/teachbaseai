"""Модели биллинга."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, Text

from apps.backend.database import Base


class BillingPlan(Base):
    __tablename__ = "billing_plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), nullable=False)
    max_portals = Column(Integer)
    max_dialogs = Column(Integer)
    price = Column(Numeric(10, 2))


class PortalBilling(Base):
    __tablename__ = "portal_billing"

    id = Column(Integer, primary_key=True, index=True)
    portal_id = Column(Integer, ForeignKey("portals.id"), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("billing_plans.id"), index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class UsageCounter(Base):
    __tablename__ = "usage_counters"

    id = Column(Integer, primary_key=True, index=True)
    portal_id = Column(Integer, ForeignKey("portals.id"), nullable=False, index=True)
    counter_type = Column(String(32), nullable=False)  # dialogs, messages
    value = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PortalUsageLimit(Base):
    __tablename__ = "portal_usage_limits"

    portal_id = Column(Integer, ForeignKey("portals.id"), primary_key=True)
    monthly_request_limit = Column(Integer, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BillingUsage(Base):
    __tablename__ = "billing_usage"

    id = Column(Integer, primary_key=True, index=True)
    portal_id = Column(Integer, ForeignKey("portals.id"), nullable=False, index=True)
    user_id = Column(String(64), nullable=True, index=True)
    request_id = Column(String(128), nullable=True, index=True)
    kind = Column(String(32), nullable=False, default="chat")  # chat|embedding
    model = Column(String(128), nullable=True)
    tokens_prompt = Column(Integer, nullable=True)
    tokens_completion = Column(Integer, nullable=True)
    tokens_total = Column(Integer, nullable=True)
    cost_rub = Column(Numeric(12, 6), nullable=True)
    status = Column(String(32), nullable=False, default="ok")  # ok|blocked|error
    error_code = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
