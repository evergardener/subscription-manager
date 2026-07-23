import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.models.tables import (
    ActorType,
    BillingEvent,
    DeliveryStatus,
    EventStatus,
    ReminderDelivery,
    ReminderRule,
    Subscription,
)
from app.services.business import roll_billing_events


class ReminderStateError(RuntimeError):
    pass


@dataclass(frozen=True)
class ScanResult:
    generated_events: int = 0
    generated: int = 0
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
            .join(Subscription, Subscription.id == BillingEvent.subscription_id)
            .where(
                ReminderRule.enabled.is_(True),
                BillingEvent.status == EventStatus.PLANNED,
                BillingEvent.event_date <= event_end,
                Subscription.archived_at.is_(None),
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
        existing.add(key)
        generated += 1
        expired += int(is_expired)
    await session.flush()
    return generated, expired


async def maintain_events_and_outbox(
    factory: async_sessionmaker[AsyncSession], settings: Settings, dry_run: bool = False
) -> ScanResult:
    now = datetime.now(UTC)
    async with factory() as session:
        generated_events = await roll_billing_events(session)
        generated = expired = 0
        if settings.notification_mode == "external":
            generated, expired = await generate_deliveries(session, settings, now)
        result = ScanResult(generated_events, generated, expired, dry_run)
        if dry_run:
            await session.rollback()
        else:
            await session.commit()
        return result


async def claim_deliveries(
    session: AsyncSession,
    settings: Settings,
    now: datetime,
    actor_type: ActorType,
    actor_id: str,
    limit: int = 100,
) -> list[uuid.UUID]:
    statement = (
        select(ReminderDelivery)
        .join(ReminderRule, ReminderRule.id == ReminderDelivery.rule_id)
        .join(Subscription, Subscription.id == ReminderRule.subscription_id)
        .where(
            Subscription.archived_at.is_(None),
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
        record.claimed_by_actor_type = actor_type
        record.claimed_by_actor_id = actor_id
    await session.commit()
    return [record.id for record in records]


def _require_claim_owner(
    delivery: ReminderDelivery, actor_type: ActorType, actor_id: str, now: datetime
) -> None:
    if delivery.claimed_by_actor_type != actor_type or delivery.claimed_by_actor_id != actor_id:
        raise ReminderStateError("reminder delivery is leased to another actor")
    if delivery.status != DeliveryStatus.PROCESSING:
        raise ReminderStateError("reminder delivery is not processing")
    if delivery.lease_expires_at is None or delivery.lease_expires_at <= now:
        raise ReminderStateError("reminder delivery lease has expired")


def acknowledge_delivery(
    delivery: ReminderDelivery, actor_type: ActorType, actor_id: str, now: datetime
) -> None:
    _require_claim_owner(delivery, actor_type, actor_id, now)
    delivery.status = DeliveryStatus.SENT
    delivery.sent_at = now
    delivery.error = None
    delivery.next_attempt_at = None
    delivery.lease_expires_at = None
    delivery.version += 1


def fail_delivery(
    delivery: ReminderDelivery,
    actor_type: ActorType,
    actor_id: str,
    settings: Settings,
    now: datetime,
    error: str,
) -> None:
    _require_claim_owner(delivery, actor_type, actor_id, now)
    delivery.status = (
        DeliveryStatus.DEAD
        if delivery.attempt_count >= settings.reminder_max_attempts
        else DeliveryStatus.FAILED
    )
    delivery.error = error[:1000]
    if delivery.status == DeliveryStatus.FAILED:
        delay_minutes = min(2 ** max(delivery.attempt_count - 1, 0), 60)
        delivery.next_attempt_at = now + timedelta(minutes=delay_minutes)
    delivery.lease_expires_at = None
    delivery.version += 1
