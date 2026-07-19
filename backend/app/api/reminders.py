import uuid
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import Actor, get_actor
from app.core.config import Settings, get_settings
from app.core.database import get_session, get_session_factory
from app.core.request_context import request_id_context
from app.models.tables import (
    BillingEvent,
    DeliveryStatus,
    ReminderDelivery,
    ReminderRule,
    Subscription,
)
from app.services.business import add_audit, model_dict
from app.services.reminders import (
    ReminderStateError,
    acknowledge_delivery,
    claim_deliveries,
    fail_delivery,
    maintain_events_and_outbox,
)

router = APIRouter(prefix="/api/v1/reminders", tags=["reminders"])


class ClaimInput(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)


class FailureInput(BaseModel):
    error: str = Field(min_length=1, max_length=1000)


async def delivery_json(session: AsyncSession, item: ReminderDelivery) -> dict[str, Any]:
    rule = await session.get(ReminderRule, item.rule_id)
    if rule is None:
        raise HTTPException(status_code=409, detail="reminder rule no longer exists")
    subscription = await session.get(Subscription, rule.subscription_id)
    if subscription is None:
        raise HTTPException(status_code=409, detail="subscription no longer exists")
    local_schedule = item.scheduled_for.astimezone(ZoneInfo("Asia/Shanghai"))
    event_date = local_schedule.date() + timedelta(days=rule.offset_days)
    event = await session.scalar(
        select(BillingEvent).where(
            BillingEvent.subscription_id == subscription.id,
            BillingEvent.event_type == rule.event_type,
            BillingEvent.event_date == event_date,
        )
    )
    amount: Decimal | None = event.amount if event else None
    return {
        "id": str(item.id),
        "event_key": item.event_key,
        "scheduled_for": item.scheduled_for,
        "lease_expires_at": item.lease_expires_at,
        "attempt_count": item.attempt_count,
        "subscription_id": str(subscription.id),
        "subscription_name": subscription.name,
        "event_type": rule.event_type.value,
        "event_date": event_date,
        "offset_days": rule.offset_days,
        "amount": amount,
        "currency": event.currency if event else None,
    }


@router.post("/scan")
async def scan_reminders(
    dry_run: bool = Query(default=False), actor: Actor = Depends(get_actor)
) -> dict[str, int | bool]:
    actor.require("reminders:scan")
    result = await maintain_events_and_outbox(
        get_session_factory(), get_settings(), dry_run=dry_run
    )
    return asdict(result)


@router.post("/claim")
async def claim_due_reminders(
    payload: ClaimInput,
    actor: Actor = Depends(get_actor),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> list[dict[str, Any]]:
    actor.require("reminders:consume")
    if settings.notification_mode != "external":
        raise HTTPException(status_code=409, detail="external notifications are disabled")
    now = datetime.now(UTC)
    ids = await claim_deliveries(
        session, settings, now, actor.actor_type, actor.actor_id, payload.limit
    )
    results: list[dict[str, Any]] = []
    for delivery_id in ids:
        item = await session.get(ReminderDelivery, delivery_id)
        if item is None:
            continue
        add_audit(
            session,
            actor,
            "claim",
            "reminder_delivery",
            item.id,
            request_id_context.get() or "unknown",
            None,
            model_dict(item),
        )
        results.append(await delivery_json(session, item))
    await session.commit()
    return results


@router.post("/deliveries/{delivery_id}/ack")
async def acknowledge_due_reminder(
    delivery_id: uuid.UUID,
    actor: Actor = Depends(get_actor),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    actor.require("reminders:consume")
    item = await session.get(ReminderDelivery, delivery_id, with_for_update=True)
    if item is None:
        raise HTTPException(status_code=404, detail="delivery not found")
    before = model_dict(item)
    try:
        acknowledge_delivery(item, actor.actor_type, actor.actor_id, datetime.now(UTC))
    except ReminderStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    add_audit(
        session,
        actor,
        "acknowledge",
        "reminder_delivery",
        item.id,
        request_id_context.get() or "unknown",
        before,
        model_dict(item),
    )
    result = {**model_dict(item), "status": item.status.value}
    await session.commit()
    return result


@router.post("/deliveries/{delivery_id}/fail")
async def fail_due_reminder(
    delivery_id: uuid.UUID,
    payload: FailureInput,
    actor: Actor = Depends(get_actor),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    actor.require("reminders:consume")
    item = await session.get(ReminderDelivery, delivery_id, with_for_update=True)
    if item is None:
        raise HTTPException(status_code=404, detail="delivery not found")
    before = model_dict(item)
    try:
        fail_delivery(
            item,
            actor.actor_type,
            actor.actor_id,
            settings,
            datetime.now(UTC),
            payload.error,
        )
    except ReminderStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    add_audit(
        session,
        actor,
        "fail",
        "reminder_delivery",
        item.id,
        request_id_context.get() or "unknown",
        before,
        model_dict(item),
    )
    result = {**model_dict(item), "status": item.status.value}
    await session.commit()
    return result


@router.get("/deliveries")
async def list_deliveries(
    status: DeliveryStatus | None = None,
    actor: Actor = Depends(get_actor),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, object]]:
    actor.require("reminders:read")
    statement = select(ReminderDelivery).order_by(ReminderDelivery.scheduled_for.desc()).limit(200)
    if status is not None:
        statement = statement.where(ReminderDelivery.status == status)
    items = (await session.scalars(statement)).all()
    return [{**model_dict(item), "status": item.status.value} for item in items]


@router.post("/deliveries/{delivery_id}/retry")
async def retry_delivery(
    delivery_id: uuid.UUID,
    actor: Actor = Depends(get_actor),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    actor.require("reminders:retry")
    item = await session.get(ReminderDelivery, delivery_id, with_for_update=True)
    if item is None:
        raise HTTPException(status_code=404, detail="delivery not found")
    if item.status not in {DeliveryStatus.FAILED, DeliveryStatus.DEAD}:
        raise HTTPException(status_code=422, detail="only failed or dead deliveries can be retried")
    before = model_dict(item)
    item.status = DeliveryStatus.PENDING
    item.attempt_count = 0
    item.next_attempt_at = datetime.now(UTC)
    item.lease_expires_at = None
    item.claimed_by_actor_type = None
    item.claimed_by_actor_id = None
    item.error = None
    item.version += 1
    add_audit(
        session,
        actor,
        "retry",
        "reminder_delivery",
        item.id,
        request_id_context.get() or "unknown",
        before,
        model_dict(item),
    )
    await session.commit()
    return {**model_dict(item), "status": item.status.value}
