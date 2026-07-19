import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    ARRAY,
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.db.metadata import metadata


class Base(DeclarativeBase):
    metadata = metadata


def enum_values(enum_class: type[enum.Enum]) -> list[str]:
    return [str(member.value) for member in enum_class]


class ActorType(enum.StrEnum):
    USER = "user"
    HERMES = "hermes"
    SYSTEM = "system"
    IMPORT = "import"


class SubscriptionStatus(enum.StrEnum):
    ACTIVE = "active"
    TRIAL = "trial"
    PENDING_CANCEL = "pending_cancel"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class EventType(enum.StrEnum):
    BILLING = "billing"
    EXPIRY = "expiry"
    TRIAL_END = "trial_end"
    CANCELLATION_DEADLINE = "cancellation_deadline"
    CONTRACT_END = "contract_end"


class EventStatus(enum.StrEnum):
    PLANNED = "planned"
    RECONCILED = "reconciled"
    SUPERSEDED = "superseded"
    CANCELLED = "cancelled"


class DeliveryStatus(enum.StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    DEAD = "dead"
    EXPIRED = "expired"


class TimestampVersionMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class Category(TimestampVersionMixin, Base):
    __tablename__ = "categories"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    normalized_name: Mapped[str] = mapped_column(String(200), unique=True)
    icon: Mapped[str | None] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Tag(TimestampVersionMixin, Base):
    __tablename__ = "tags"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    normalized_name: Mapped[str] = mapped_column(String(200), unique=True)
    color: Mapped[str | None] = mapped_column(String(30))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Subscription(TimestampVersionMixin, Base):
    __tablename__ = "subscriptions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    vendor: Mapped[str | None] = mapped_column(String(200))
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT")
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name="subscription_status", values_callable=enum_values)
    )
    website: Mapped[str | None] = mapped_column(Text)
    logo_url: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    payment_method_description: Mapped[str | None] = mapped_column(String(200))
    start_date: Mapped[date | None] = mapped_column(Date)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BillingPlan(TimestampVersionMixin, Base):
    __tablename__ = "billing_plans"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="billing_plan_amount_nonnegative"),
        CheckConstraint(
            "interval_count BETWEEN 1 AND 120", name="billing_plan_interval_count_range"
        ),
        CheckConstraint("currency = upper(currency)", name="billing_plan_currency_uppercase"),
        Index(
            "uq_current_billing_plan",
            "subscription_id",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="RESTRICT"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    currency: Mapped[str] = mapped_column(String(3))
    interval_unit: Mapped[str] = mapped_column(String(10))
    interval_count: Mapped[int] = mapped_column(Integer)
    anchor_date: Mapped[date] = mapped_column(Date)
    next_billing_date: Mapped[date | None] = mapped_column(Date)
    auto_renew: Mapped[bool] = mapped_column(Boolean)
    billing_mode: Mapped[str] = mapped_column(String(20))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BillingEvent(TimestampVersionMixin, Base):
    __tablename__ = "billing_events"
    __table_args__ = (
        UniqueConstraint("billing_plan_id", "event_type", "event_date", name="uq_plan_event_date"),
        Index(
            "uq_lifecycle_event_date",
            "subscription_id",
            "event_type",
            "event_date",
            unique=True,
            postgresql_where=text("billing_plan_id IS NULL"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="RESTRICT"), index=True
    )
    billing_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billing_plans.id", ondelete="RESTRICT")
    )
    event_type: Mapped[EventType] = mapped_column(
        Enum(EventType, name="event_type", values_callable=enum_values)
    )
    event_date: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    currency: Mapped[str | None] = mapped_column(String(3))
    status: Mapped[EventStatus] = mapped_column(
        Enum(EventStatus, name="event_status", values_callable=enum_values),
        default=EventStatus.PLANNED,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ServiceDates(TimestampVersionMixin, Base):
    __tablename__ = "service_dates"
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="RESTRICT"), primary_key=True
    )
    trial_end_date: Mapped[date | None] = mapped_column(Date)
    service_expiry_date: Mapped[date | None] = mapped_column(Date)
    cancellation_deadline: Mapped[date | None] = mapped_column(Date)
    contract_end_date: Mapped[date | None] = mapped_column(Date)


class Payment(TimestampVersionMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("source", "external_ref", name="uq_payment_external_ref"),
        CheckConstraint("amount > 0", name="payment_amount_positive"),
        CheckConstraint("tax_amount >= 0 AND tax_amount <= amount", name="payment_tax_range"),
        CheckConstraint("currency = upper(currency)", name="payment_currency_uppercase"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="RESTRICT"), index=True
    )
    billing_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billing_events.id", ondelete="RESTRICT")
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    currency: Mapped[str] = mapped_column(String(3))
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0)
    source: Mapped[str] = mapped_column(String(50))
    external_ref: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)


class ReminderRule(TimestampVersionMixin, Base):
    __tablename__ = "reminder_rules"
    __table_args__ = (
        UniqueConstraint(
            "subscription_id", "event_type", "offset_days", "channel", name="uq_reminder_rule"
        ),
        CheckConstraint("offset_days BETWEEN 0 AND 3650", name="reminder_offset_range"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="RESTRICT"), index=True
    )
    event_type: Mapped[EventType] = mapped_column(
        Enum(EventType, name="event_type", values_callable=enum_values)
    )
    offset_days: Mapped[int] = mapped_column(Integer)
    channel: Mapped[str] = mapped_column(String(50))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class ReminderDelivery(TimestampVersionMixin, Base):
    __tablename__ = "reminder_deliveries"
    __table_args__ = (
        CheckConstraint("attempt_count >= 0", name="delivery_attempt_count_nonnegative"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reminder_rules.id", ondelete="RESTRICT"), index=True
    )
    event_key: Mapped[str] = mapped_column(String(500), unique=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[DeliveryStatus] = mapped_column(
        Enum(DeliveryStatus, name="delivery_status", values_callable=enum_values),
        default=DeliveryStatus.PENDING,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claimed_by_actor_type: Mapped[ActorType | None] = mapped_column(
        Enum(ActorType, name="actor_type", values_callable=enum_values)
    )
    claimed_by_actor_id: Mapped[str | None] = mapped_column(String(200))


class SubscriptionTag(Base):
    __tablename__ = "subscription_tags"
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tags.id", ondelete="RESTRICT"), primary_key=True
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    actor_type: Mapped[ActorType] = mapped_column(
        Enum(ActorType, name="actor_type", values_callable=enum_values)
    )
    actor_id: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    before_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    request_id: Mapped[str] = mapped_column(String(100))
    idempotency_key_hash: Mapped[str | None] = mapped_column(String(128))


class User(TimestampVersionMixin, Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(100))
    normalized_username: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    password_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    csrf_hash: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    idle_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ApiToken(TimestampVersionMixin, Base):
    __tablename__ = "api_tokens"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    actor_type: Mapped[ActorType] = mapped_column(
        Enum(ActorType, name="actor_type", values_callable=enum_values)
    )
    actor_id: Mapped[str] = mapped_column(String(200))
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[str] = mapped_column(String(200))
    method: Mapped[str] = mapped_column(String(10))
    path: Mapped[str] = mapped_column(String(500))
    key_hash: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(128))
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("actor_id", "method", "path", "key_hash", name="uq_idempotency_scope"),
    )
