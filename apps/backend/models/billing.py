"""Billing models."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from apps.backend.database import Base


class BillingPlan(Base):
    __tablename__ = "billing_plans"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(32), nullable=True, unique=True, index=True)
    name = Column(String(64), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    max_portals = Column(Integer)
    max_dialogs = Column(Integer)
    price = Column(Numeric(10, 2))
    price_month = Column(Numeric(10, 2), nullable=True)
    currency = Column(String(16), nullable=True)
    limits_json = Column(JSONB, nullable=True)
    features_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


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
    counter_type = Column(String(32), nullable=False)
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
    kind = Column(String(32), nullable=False, default="chat")
    model = Column(String(128), nullable=True)
    tokens_prompt = Column(Integer, nullable=True)
    tokens_completion = Column(Integer, nullable=True)
    tokens_total = Column(Integer, nullable=True)
    cost_rub = Column(Numeric(12, 6), nullable=True)
    status = Column(String(32), nullable=False, default="ok")
    error_code = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AccountSubscription(Base):
    __tablename__ = "account_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("billing_plans.id", ondelete="RESTRICT"), nullable=False, index=True)
    plan_version_id = Column(Integer, ForeignKey("billing_plan_versions.id", ondelete="RESTRICT"), nullable=True, index=True)
    status = Column(String(32), nullable=False, default="trial")
    billing_cycle = Column(String(32), nullable=False, default="monthly")
    trial_until = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class AccountPlanOverride(Base):
    __tablename__ = "account_plan_overrides"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    limits_json = Column(JSONB, nullable=True)
    features_json = Column(JSONB, nullable=True)
    valid_from = Column(DateTime, nullable=True)
    valid_to = Column(DateTime, nullable=True)
    reason = Column(String(255), nullable=True)
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class BillingPlanVersion(Base):
    __tablename__ = "billing_plan_versions"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("billing_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    version_code = Column(String(64), nullable=False, unique=True, index=True)
    name = Column(String(128), nullable=False)
    price_month = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(16), nullable=False, default="RUB")
    limits_json = Column(JSONB, nullable=True)
    features_json = Column(JSONB, nullable=True)
    valid_from = Column(DateTime, nullable=True)
    valid_to = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    is_default_for_new_accounts = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class BillingCohort(Base):
    __tablename__ = "billing_cohorts"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(64), nullable=False, unique=True, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    rule_json = Column(JSONB, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class BillingCohortAssignment(Base):
    __tablename__ = "billing_cohort_assignments"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    cohort_id = Column(Integer, ForeignKey("billing_cohorts.id", ondelete="CASCADE"), nullable=False, index=True)
    source = Column(String(32), nullable=False, default="manual")
    reason = Column(String(255), nullable=True)
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class BillingCohortPolicy(Base):
    __tablename__ = "billing_cohort_policies"

    id = Column(Integer, primary_key=True, index=True)
    cohort_id = Column(Integer, ForeignKey("billing_cohorts.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_version_id = Column(Integer, ForeignKey("billing_plan_versions.id", ondelete="RESTRICT"), nullable=False, index=True)
    discount_type = Column(String(32), nullable=False, default="none")
    discount_value = Column(Numeric(12, 2), nullable=True)
    feature_adjustments_json = Column(JSONB, nullable=True)
    limit_adjustments_json = Column(JSONB, nullable=True)
    valid_from = Column(DateTime, nullable=True)
    valid_to = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class BillingAccountAdjustment(Base):
    __tablename__ = "billing_account_adjustments"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String(64), nullable=False, index=True)
    target_key = Column(String(128), nullable=True)
    value_json = Column(JSONB, nullable=True)
    valid_from = Column(DateTime, nullable=True)
    valid_to = Column(DateTime, nullable=True)
    reason = Column(String(255), nullable=True)
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class BillingPaymentAttempt(Base):
    __tablename__ = "billing_payment_attempts"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    subscription_id = Column(Integer, ForeignKey("account_subscriptions.id", ondelete="SET NULL"), nullable=True, index=True)
    plan_id = Column(Integer, ForeignKey("billing_plans.id", ondelete="SET NULL"), nullable=True, index=True)
    plan_version_id = Column(Integer, ForeignKey("billing_plan_versions.id", ondelete="SET NULL"), nullable=True, index=True)
    provider = Column(String(32), nullable=False, default="yookassa")
    idempotence_key = Column(String(128), nullable=False, unique=True, index=True)
    provider_payment_id = Column(String(128), nullable=True, unique=True, index=True)
    status = Column(String(32), nullable=False, default="pending")
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(16), nullable=False, default="RUB")
    description = Column(Text, nullable=True)
    confirmation_url = Column(Text, nullable=True)
    return_url = Column(Text, nullable=True)
    paid = Column(Boolean, nullable=False, default=False)
    test = Column(Boolean, nullable=False, default=False)
    error_message = Column(Text, nullable=True)
    provider_payload_json = Column(JSONB, nullable=True)
    metadata_json = Column(JSONB, nullable=True)
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    succeeded_at = Column(DateTime, nullable=True)
    canceled_at = Column(DateTime, nullable=True)
