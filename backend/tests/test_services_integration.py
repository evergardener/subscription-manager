import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import Actor
from app.core.config import get_settings
from app.core.database import get_session_factory
from app.models.tables import (
    ActorType,
    BillingEvent,
    BillingPlan,
    DeliveryStatus,
    EventStatus,
    EventType,
    ReminderDelivery,
    ReminderRule,
    Subscription,
    SubscriptionStatus,
)
from app.notifications.ntfy import Notification, NotificationError
from app.services.business import (
    add_audit,
    add_idempotency,
    advance_plan,
    find_idempotency,
    generate_billing_events,
    model_dict,
    replace_plan,
)
from app.services.reminders import (
    _deliver_one,
    claim_deliveries,
    generate_deliveries,
    scheduled_at,
)


async def test_business_services_generate_replace_audit_and_idempotency(
    db_session: AsyncSession,
) -> None:
    subscription = Subscription(name=f"service-{uuid.uuid4()}", status=SubscriptionStatus.ACTIVE)
    db_session.add(subscription)
    await db_session.flush()
    old = BillingPlan(
        subscription_id=subscription.id,
        amount=Decimal("100"),
        currency="USD",
        interval_unit="month",
        interval_count=1,
        anchor_date=date(2026, 7, 31),
        next_billing_date=date(2026, 7, 31),
        auto_renew=True,
        billing_mode="fixed",
    )
    db_session.add(old)
    await db_session.flush()
    assert await generate_billing_events(db_session, old, date(2026, 10, 31)) == 4
    assert await generate_billing_events(db_session, old, date(2026, 10, 31)) == 0
    old.auto_renew = False
    assert await generate_billing_events(db_session, old, date(2026, 12, 31)) == 0
    old.auto_renew = True
    assert advance_plan(old, date(2026, 7, 31)) == date(2026, 8, 31)

    now = datetime.now(UTC)
    replacement = BillingPlan(
        subscription_id=subscription.id,
        amount=Decimal("120"),
        currency="USD",
        interval_unit="month",
        interval_count=1,
        anchor_date=date(2026, 8, 15),
        next_billing_date=date(2026, 8, 15),
        auto_renew=True,
        billing_mode="fixed",
    )
    await replace_plan(db_session, old, replacement, now)
    actor = Actor(ActorType.USER, "integration-admin", frozenset({"*"}))
    add_audit(
        db_session,
        actor,
        "update",
        "subscription",
        subscription.id,
        "integration-request",
        model_dict(subscription),
        model_dict(subscription),
        "audit-key",
    )
    response = {"id": subscription.id, "amount": Decimal("120")}
    payload = {"name": subscription.name}
    add_idempotency(
        db_session,
        actor.actor_id,
        "POST",
        "/api/v1/subscriptions",
        "same-key",
        payload,
        response,
        201,
    )
    await db_session.commit()
    cached = await find_idempotency(
        db_session,
        actor.actor_id,
        "POST",
        "/api/v1/subscriptions",
        "same-key",
        payload,
    )
    assert cached == {"id": str(subscription.id), "amount": "120"}


class SuccessfulAdapter:
    async def send(self, notification: Notification) -> None:
        assert notification is not None


class FailingAdapter:
    async def send(self, notification: Notification) -> None:
        del notification
        raise NotificationError("simulated failure")


async def test_reminder_services_generate_claim_send_retry_and_dead(
    db_session: AsyncSession,
) -> None:
    settings = get_settings().model_copy(
        update={"reminder_scan_days": 366, "reminder_grace_days": 3, "reminder_max_attempts": 2}
    )
    subscription = Subscription(name=f"reminder-{uuid.uuid4()}", status=SubscriptionStatus.ACTIVE)
    db_session.add(subscription)
    await db_session.flush()
    event = BillingEvent(
        subscription_id=subscription.id,
        event_type=EventType.BILLING,
        event_date=date.today() + timedelta(days=1),
        status=EventStatus.PLANNED,
        amount=Decimal("10"),
        currency="USD",
    )
    rule = ReminderRule(
        subscription_id=subscription.id,
        event_type=EventType.BILLING,
        offset_days=1,
        channel="ntfy",
    )
    db_session.add_all([event, rule])
    await db_session.commit()
    now = scheduled_at(event.event_date, rule.offset_days) + timedelta(minutes=1)
    assert await generate_deliveries(db_session, settings, now) == (1, 0)
    assert await generate_deliveries(db_session, settings, now) == (0, 0)
    claimed = await claim_deliveries(db_session, settings, now)
    assert len(claimed) == 1
    assert (
        await _deliver_one(db_session, claimed[0], SuccessfulAdapter(), settings, now)
        == DeliveryStatus.SENT
    )

    failed = ReminderDelivery(
        rule_id=rule.id,
        event_key=f"failure-{uuid.uuid4()}",
        scheduled_for=now - timedelta(minutes=1),
        status=DeliveryStatus.PROCESSING,
        attempt_count=1,
    )
    db_session.add(failed)
    await db_session.commit()
    assert (
        await _deliver_one(db_session, failed.id, FailingAdapter(), settings, now)
        == DeliveryStatus.FAILED
    )
    failed.status = DeliveryStatus.PROCESSING
    failed.attempt_count = 2
    await db_session.commit()
    assert (
        await _deliver_one(db_session, failed.id, FailingAdapter(), settings, now)
        == DeliveryStatus.DEAD
    )
    statuses = set(await db_session.scalars(select(ReminderDelivery.status)))
    assert {DeliveryStatus.SENT, DeliveryStatus.DEAD} <= statuses


async def test_concurrent_claimers_never_claim_the_same_delivery(
    db_session: AsyncSession,
) -> None:
    settings = get_settings()
    subscription = Subscription(name=f"concurrent-{uuid.uuid4()}", status=SubscriptionStatus.ACTIVE)
    db_session.add(subscription)
    await db_session.flush()
    rule = ReminderRule(
        subscription_id=subscription.id,
        event_type=EventType.BILLING,
        offset_days=0,
        channel="ntfy",
    )
    db_session.add(rule)
    await db_session.flush()
    delivery = ReminderDelivery(
        rule_id=rule.id,
        event_key=f"concurrent-{uuid.uuid4()}",
        scheduled_for=datetime.now(UTC) - timedelta(minutes=1),
        status=DeliveryStatus.PENDING,
    )
    db_session.add(delivery)
    await db_session.commit()

    factory = get_session_factory()
    async with factory() as first, factory() as second:
        first_ids = await claim_deliveries(first, settings, datetime.now(UTC))
        second_ids = await claim_deliveries(second, settings, datetime.now(UTC))
    assert first_ids == [delivery.id]
    assert second_ids == []
