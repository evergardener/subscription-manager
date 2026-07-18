from datetime import date
from decimal import Decimal

import pytest

from app.domain.billing import (
    DomainError,
    IntervalUnit,
    SubscriptionStatus,
    next_occurrence,
    occurrences_through,
    validate_money,
    validate_transition,
)


@pytest.mark.parametrize(
    ("anchor", "unit", "count", "occurrence", "expected"),
    [
        (date(2025, 1, 31), IntervalUnit.MONTH, 1, 1, date(2025, 2, 28)),
        (date(2025, 1, 31), IntervalUnit.MONTH, 1, 2, date(2025, 3, 31)),
        (date(2024, 2, 29), IntervalUnit.YEAR, 1, 1, date(2025, 2, 28)),
        (date(2024, 2, 29), IntervalUnit.YEAR, 1, 4, date(2028, 2, 29)),
        (date(2026, 1, 15), IntervalUnit.MONTH, 3, 1, date(2026, 4, 15)),
        (date(2026, 1, 15), IntervalUnit.MONTH, 6, 1, date(2026, 7, 15)),
    ],
)
def test_calendar_occurrences_preserve_anchor(
    anchor: date,
    unit: IntervalUnit,
    count: int,
    occurrence: int,
    expected: date,
) -> None:
    assert next_occurrence(anchor, unit, count, occurrence) == expected


def test_occurrence_generation_uses_decimal_and_currency() -> None:
    items = occurrences_through(
        date(2026, 1, 31),
        IntervalUnit.MONTH,
        1,
        Decimal("10.123456"),
        "usd",
        date(2026, 2, 1),
        date(2026, 3, 31),
    )
    assert [(item.event_date, item.amount, item.currency) for item in items] == [
        (date(2026, 2, 28), Decimal("10.123456"), "USD"),
        (date(2026, 3, 31), Decimal("10.123456"), "USD"),
    ]


def test_money_rejects_negative_and_invalid_currency() -> None:
    with pytest.raises(DomainError):
        validate_money(Decimal("-1"), "USD")
    with pytest.raises(DomainError):
        validate_money(Decimal("1"), "US")


def test_status_machine_accepts_and_rejects_transitions() -> None:
    validate_transition(SubscriptionStatus.ACTIVE, SubscriptionStatus.PENDING_CANCEL)
    with pytest.raises(DomainError):
        validate_transition(SubscriptionStatus.ACTIVE, SubscriptionStatus.CANCELLED)
