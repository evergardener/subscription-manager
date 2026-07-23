import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
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
    ReminderStateError,
    acknowledge_delivery,
    claim_deliveries,
    fail_delivery,
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
    subscription.archived_at = datetime.now(UTC)
    assert await generate_billing_events(db_session, old, date(2026, 12, 31)) == 0
    subscription.archived_at = None
    await db_session.flush()
    await db_session.refresh(subscription)
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


async def test_reminder_services_generate_claim_ack_retry_and_dead(
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
        channel="external",
    )
    db_session.add_all([event, rule])
    await db_session.commit()
    now = scheduled_at(event.event_date, rule.offset_days) + timedelta(minutes=1)
    subscription.archived_at = datetime.now(UTC)
    await db_session.commit()
    assert await generate_deliveries(db_session, settings, now) == (0, 0)
    subscription.archived_at = None
    await db_session.commit()
    assert await generate_deliveries(db_session, settings, now) == (1, 0)
    assert await generate_deliveries(db_session, settings, now) == (0, 0)
    subscription.archived_at = datetime.now(UTC)
    await db_session.commit()
    assert (
        await claim_deliveries(db_session, settings, now, ActorType.HERMES, "hermes-primary") == []
    )
    subscription.archived_at = None
    await db_session.commit()
    claimed = await claim_deliveries(db_session, settings, now, ActorType.HERMES, "hermes-primary")
    assert len(claimed) == 1
    sent = await db_session.get(ReminderDelivery, claimed[0])
    assert sent is not None
    with pytest.raises(ReminderStateError, match="another actor"):
        acknowledge_delivery(sent, ActorType.HERMES, "hermes-secondary", now)
    acknowledge_delivery(sent, ActorType.HERMES, "hermes-primary", now)
    assert sent.status == DeliveryStatus.SENT

    expired_lease = ReminderDelivery(
        rule_id=rule.id,
        event_key=f"expired-lease-{uuid.uuid4()}",
        scheduled_for=now - timedelta(minutes=2),
        status=DeliveryStatus.PROCESSING,
        attempt_count=1,
        lease_expires_at=now,
        claimed_by_actor_type=ActorType.HERMES,
        claimed_by_actor_id="hermes-primary",
    )
    with pytest.raises(ReminderStateError, match="lease has expired"):
        acknowledge_delivery(expired_lease, ActorType.HERMES, "hermes-primary", now)

    failed = ReminderDelivery(
        rule_id=rule.id,
        event_key=f"failure-{uuid.uuid4()}",
        scheduled_for=now - timedelta(minutes=1),
        status=DeliveryStatus.PROCESSING,
        attempt_count=1,
        lease_expires_at=now + timedelta(minutes=1),
        claimed_by_actor_type=ActorType.HERMES,
        claimed_by_actor_id="hermes-primary",
    )
    db_session.add(failed)
    await db_session.commit()
    fail_delivery(
        failed,
        ActorType.HERMES,
        "hermes-primary",
        settings,
        now,
        "simulated failure",
    )
    assert failed.status == DeliveryStatus.FAILED
    failed.status = DeliveryStatus.PROCESSING
    failed.attempt_count = 2
    failed.lease_expires_at = now + timedelta(minutes=1)
    await db_session.commit()
    fail_delivery(
        failed,
        ActorType.HERMES,
        "hermes-primary",
        settings,
        now,
        "simulated failure",
    )
    assert failed.status == DeliveryStatus.DEAD
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
        channel="external",
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
        first_ids = await claim_deliveries(
            first, settings, datetime.now(UTC), ActorType.HERMES, "first"
        )
        second_ids = await claim_deliveries(
            second, settings, datetime.now(UTC), ActorType.HERMES, "second"
        )
    assert first_ids == [delivery.id]
    assert second_ids == []
