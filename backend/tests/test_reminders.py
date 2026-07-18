import uuid
from datetime import UTC, date, datetime

from app.models.tables import BillingEvent, EventStatus, EventType, ReminderRule
from app.services.reminders import event_key, scheduled_at


def test_event_key_is_stable_and_complete() -> None:
    subscription_id = uuid.uuid4()
    event = BillingEvent(
        subscription_id=subscription_id,
        event_type=EventType.BILLING,
        event_date=date(2026, 8, 21),
        status=EventStatus.PLANNED,
    )
    rule = ReminderRule(
        subscription_id=subscription_id,
        event_type=EventType.BILLING,
        offset_days=5,
        channel="ntfy",
    )
    assert event_key(event, rule) == f"{subscription_id}:billing:2026-08-21:5:ntfy"


def test_scheduled_time_uses_asia_shanghai_and_utc_storage() -> None:
    assert scheduled_at(date(2026, 8, 21), 5) == datetime(2026, 8, 16, 1, tzinfo=UTC)
