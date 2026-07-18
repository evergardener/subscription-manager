import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.models.tables import (
    BillingEvent,
    DeliveryStatus,
    EventStatus,
    ReminderDelivery,
    ReminderRule,
    Subscription,
)
from app.notifications.ntfy import Notification, NotificationError, NtfyAdapter
from app.services.business import roll_billing_events


class NotificationSender(Protocol):
    async def send(self, notification: Notification) -> None: ...


@dataclass(frozen=True)
class ScanResult:
    generated_events: int = 0
    generated: int = 0
    claimed: int = 0
    sent: int = 0
    failed: int = 0
    dead: int = 0
    expired: int = 0
    dry_run: bool = False


def event_key(event: BillingEvent, rule: ReminderRule) -> str:
    return ":".join(
        (
            str(event.subscription_id),
            event.event_type.value,
            event.event_date.isoformat(),
            str(rule.offset_days),
            rule.channel,
        )
    )


def scheduled_at(event_date: date, offset_days: int) -> datetime:
    local = datetime.combine(
        event_date - timedelta(days=offset_days), time(hour=9), ZoneInfo("Asia/Shanghai")
    )
    return local.astimezone(UTC)


async def generate_deliveries(
    session: AsyncSession, settings: Settings, now: datetime
) -> tuple[int, int]:
    schedule_end = now + timedelta(days=settings.reminder_scan_days)
    event_end = schedule_end.date() + timedelta(days=3650)
    rows = (
        await session.execute(
            select(BillingEvent, ReminderRule)
            .join(
                ReminderRule,
                (ReminderRule.subscription_id == BillingEvent.subscription_id)
                & (ReminderRule.event_type == BillingEvent.event_type),
            )
            .where(
                ReminderRule.enabled.is_(True),
                BillingEvent.status == EventStatus.PLANNED,
                BillingEvent.event_date <= event_end,
            )
        )
    ).all()
    existing = set(await session.scalars(select(ReminderDelivery.event_key)))
    generated = expired = 0
    for event, rule in rows:
        key = event_key(event, rule)
        if key in existing:
            continue
        schedule = scheduled_at(event.event_date, rule.offset_days)
        if schedule > schedule_end:
            continue
        is_expired = schedule < now - timedelta(days=settings.reminder_grace_days)
        session.add(
            ReminderDelivery(
                rule_id=rule.id,
                event_key=key,
                scheduled_for=schedule,
                status=DeliveryStatus.EXPIRED if is_expired else DeliveryStatus.PENDING,
            )
        )
        generated += 1
        expired += int(is_expired)
    await session.commit()
    return generated, expired


async def claim_deliveries(
    session: AsyncSession, settings: Settings, now: datetime, limit: int = 100
) -> list[uuid.UUID]:
    statement = (
        select(ReminderDelivery)
        .where(
            ReminderDelivery.scheduled_for <= now,
            or_(
                ReminderDelivery.status.in_([DeliveryStatus.PENDING, DeliveryStatus.FAILED]),
                (ReminderDelivery.status == DeliveryStatus.PROCESSING)
                & (ReminderDelivery.lease_expires_at < now),
            ),
            ReminderDelivery.attempt_count < settings.reminder_max_attempts,
            or_(
                ReminderDelivery.next_attempt_at.is_(None),
                ReminderDelivery.next_attempt_at <= now,
            ),
        )
        .order_by(ReminderDelivery.scheduled_for)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    records = list((await session.scalars(statement)).all())
    lease = now + timedelta(seconds=settings.reminder_lease_seconds)
    for record in records:
        record.status = DeliveryStatus.PROCESSING
        record.lease_expires_at = lease
        record.attempt_count += 1
    await session.commit()
    return [record.id for record in records]


async def _deliver_one(
    session: AsyncSession,
    delivery_id: uuid.UUID,
    adapter: NotificationSender,
    settings: Settings,
    now: datetime,
) -> DeliveryStatus:
    delivery = await session.get(ReminderDelivery, delivery_id)
    if delivery is None:
        return DeliveryStatus.FAILED
    rule = await session.get(ReminderRule, delivery.rule_id)
    if rule is None:
        delivery.status = DeliveryStatus.DEAD
        delivery.error = "reminder rule no longer exists"
        await session.commit()
        return delivery.status
    subscription = await session.get(Subscription, rule.subscription_id)
    if subscription is None:
        delivery.status = DeliveryStatus.DEAD
        delivery.error = "subscription no longer exists"
        await session.commit()
        return delivery.status
    overdue = delivery.scheduled_for < now
    message = f"{subscription.name} 的 {rule.event_type.value} 提醒"
    if overdue:
        message = f"补发: {message}"
    try:
        await adapter.send(Notification(title="Hermes Subscription Manager", message=message))
    except NotificationError as exc:
        delivery.status = (
            DeliveryStatus.DEAD
            if delivery.attempt_count >= settings.reminder_max_attempts
            else DeliveryStatus.FAILED
        )
        delivery.error = str(exc)[:1000]
        if delivery.status == DeliveryStatus.FAILED:
            delay_minutes = min(2 ** max(delivery.attempt_count - 1, 0), 60)
            delivery.next_attempt_at = now + timedelta(minutes=delay_minutes)
    else:
        delivery.status = DeliveryStatus.SENT
        delivery.sent_at = now
        delivery.error = None
        delivery.next_attempt_at = None
    delivery.lease_expires_at = None
    await session.commit()
    return delivery.status


async def scan_and_deliver(
    factory: async_sessionmaker[AsyncSession], settings: Settings, dry_run: bool = False
) -> ScanResult:
    now = datetime.now(UTC)
    async with factory() as session:
        generated_events = await roll_billing_events(session)
        generated, expired = await generate_deliveries(session, settings, now)
        if dry_run:
            return ScanResult(
                generated_events=generated_events,
                generated=generated,
                expired=expired,
                dry_run=True,
            )
        claimed = await claim_deliveries(session, settings, now)
    adapter = NtfyAdapter(settings.ntfy_base_url, settings.ntfy_topic)
    sent = failed = dead = 0
    for delivery_id in claimed:
        async with factory() as session:
            status = await _deliver_one(session, delivery_id, adapter, settings, now)
            sent += int(status == DeliveryStatus.SENT)
            failed += int(status == DeliveryStatus.FAILED)
            dead += int(status == DeliveryStatus.DEAD)
    return ScanResult(generated_events, generated, len(claimed), sent, failed, dead, expired)
