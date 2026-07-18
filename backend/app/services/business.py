import hashlib
import json
import uuid
from datetime import date, datetime, timedelta
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import Actor
from app.domain.billing import IntervalUnit, next_occurrence, occurrences_through
from app.models.tables import (
    AuditLog,
    BillingEvent,
    BillingPlan,
    EventStatus,
    EventType,
    IdempotencyRecord,
    ServiceDates,
    Subscription,
    SubscriptionStatus,
)


def model_dict(model: Any) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        {column.name: getattr(model, column.name) for column in model.__table__.columns},
    )


def json_safe(value: dict[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(json.dumps(value, default=str)))


def idempotency_hash(value: str | None) -> str | None:
    return hashlib.sha256(value.encode()).hexdigest() if value else None


def payload_hash(value: dict[str, Any]) -> str:
    encoded = json.dumps(json_safe(value), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


async def find_idempotency(
    session: AsyncSession,
    actor_id: str,
    method: str,
    path: str,
    key: str | None,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    if not key:
        return None
    record = await session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.actor_id == actor_id,
            IdempotencyRecord.method == method,
            IdempotencyRecord.path == path,
            IdempotencyRecord.key_hash == idempotency_hash(key),
        )
    )
    if record is None:
        return None
    if record.request_hash != payload_hash(payload):
        raise ValueError("Idempotency-Key was already used with a different request body")
    return record.response_json


def add_idempotency(
    session: AsyncSession,
    actor_id: str,
    method: str,
    path: str,
    key: str | None,
    payload: dict[str, Any],
    response: dict[str, Any],
    status: int,
) -> None:
    if not key:
        return
    session.add(
        IdempotencyRecord(
            actor_id=actor_id,
            method=method,
            path=path,
            key_hash=idempotency_hash(key),
            request_hash=payload_hash(payload),
            response_status=status,
            response_json=json_safe(response),
        )
    )


def add_audit(
    session: AsyncSession,
    actor: Actor,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    request_id: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    idempotency_key: str | None = None,
) -> None:
    session.add(
        AuditLog(
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_json=json_safe(before) if before else None,
            after_json=json_safe(after) if after else None,
            request_id=request_id,
            idempotency_key_hash=idempotency_hash(idempotency_key),
        )
    )


async def generate_billing_events(
    session: AsyncSession, plan: BillingPlan, through: date | None = None
) -> int:
    end = through or date.today() + timedelta(days=366)
    subscription = await session.get(Subscription, plan.subscription_id)
    if subscription and subscription.status == SubscriptionStatus.PENDING_CANCEL:
        service_dates = await session.get(ServiceDates, plan.subscription_id)
        if service_dates and service_dates.service_expiry_date:
            end = min(end, service_dates.service_expiry_date)
    start = max(plan.next_billing_date or plan.anchor_date, date.today())
    occurrences = occurrences_through(
        plan.anchor_date,
        IntervalUnit(plan.interval_unit),
        plan.interval_count,
        plan.amount,
        plan.currency,
        start,
        end,
    )
    existing = set(
        await session.scalars(
            select(BillingEvent.event_date).where(
                BillingEvent.billing_plan_id == plan.id,
                BillingEvent.event_type == EventType.BILLING,
            )
        )
    )
    created = 0
    for occurrence in occurrences:
        if occurrence.event_date not in existing:
            session.add(
                BillingEvent(
                    subscription_id=plan.subscription_id,
                    billing_plan_id=plan.id,
                    event_type=EventType.BILLING,
                    event_date=occurrence.event_date,
                    amount=occurrence.amount,
                    currency=occurrence.currency,
                    status=EventStatus.PLANNED,
                )
            )
            created += 1
    return created


async def roll_billing_events(session: AsyncSession) -> int:
    plans = (await session.scalars(select(BillingPlan).where(BillingPlan.valid_to.is_(None)))).all()
    created = 0
    for plan in plans:
        created += await generate_billing_events(session, plan)
    return created


async def generate_lifecycle_events(session: AsyncSession, dates: ServiceDates) -> int:
    mappings = (
        (EventType.TRIAL_END, dates.trial_end_date),
        (EventType.EXPIRY, dates.service_expiry_date),
        (EventType.CANCELLATION_DEADLINE, dates.cancellation_deadline),
        (EventType.CONTRACT_END, dates.contract_end_date),
    )
    existing_events = (
        await session.scalars(
            select(BillingEvent).where(
                BillingEvent.subscription_id == dates.subscription_id,
                BillingEvent.billing_plan_id.is_(None),
                BillingEvent.status == EventStatus.PLANNED,
            )
        )
    ).all()
    desired = {event_type: event_date for event_type, event_date in mappings}
    for event in existing_events:
        if desired.get(event.event_type) != event.event_date:
            event.status = EventStatus.SUPERSEDED
    existing = {
        (event.event_type, event.event_date)
        for event in existing_events
        if event.status == EventStatus.PLANNED
    }
    created = 0
    for event_type, event_date in mappings:
        if event_date is not None and (event_type, event_date) not in existing:
            session.add(
                BillingEvent(
                    subscription_id=dates.subscription_id,
                    event_type=event_type,
                    event_date=event_date,
                    status=EventStatus.PLANNED,
                )
            )
            created += 1
    return created


async def replace_plan(
    session: AsyncSession, old: BillingPlan, new: BillingPlan, now: datetime
) -> None:
    old.valid_to = now
    await session.execute(
        update(BillingEvent)
        .where(
            BillingEvent.billing_plan_id == old.id,
            BillingEvent.event_date >= date.today(),
            BillingEvent.status == EventStatus.PLANNED,
        )
        .values(status=EventStatus.SUPERSEDED)
    )
    session.add(new)
    await session.flush()
    await generate_billing_events(session, new)


def advance_plan(plan: BillingPlan, event_date: date) -> date:
    occurrence = 1
    candidate = next_occurrence(
        plan.anchor_date, IntervalUnit(plan.interval_unit), plan.interval_count, occurrence
    )
    while candidate <= event_date:
        occurrence += 1
        candidate = next_occurrence(
            plan.anchor_date, IntervalUnit(plan.interval_unit), plan.interval_count, occurrence
        )
    return candidate
