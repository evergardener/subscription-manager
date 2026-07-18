import uuid
from dataclasses import asdict
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import Actor, get_actor
from app.core.config import get_settings
from app.core.database import get_session, get_session_factory
from app.core.request_context import request_id_context
from app.models.tables import DeliveryStatus, ReminderDelivery
from app.services.business import add_audit, model_dict
from app.services.reminders import scan_and_deliver

router = APIRouter(prefix="/api/v1/reminders", tags=["reminders"])


@router.post("/scan")
async def scan_reminders(
    dry_run: bool = Query(default=False), actor: Actor = Depends(get_actor)
) -> dict[str, int | bool]:
    actor.require("reminders:scan")
    result = await scan_and_deliver(get_session_factory(), get_settings(), dry_run=dry_run)
    return asdict(result)


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
