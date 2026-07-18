from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum


class IntervalUnit(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


class SubscriptionStatus(StrEnum):
    ACTIVE = "active"
    TRIAL = "trial"
    PENDING_CANCEL = "pending_cancel"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


ALLOWED_TRANSITIONS: dict[SubscriptionStatus, frozenset[SubscriptionStatus]] = {
    SubscriptionStatus.TRIAL: frozenset(
        {
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.PENDING_CANCEL,
            SubscriptionStatus.PAUSED,
            SubscriptionStatus.EXPIRED,
        }
    ),
    SubscriptionStatus.ACTIVE: frozenset(
        {SubscriptionStatus.PENDING_CANCEL, SubscriptionStatus.PAUSED, SubscriptionStatus.EXPIRED}
    ),
    SubscriptionStatus.PENDING_CANCEL: frozenset(
        {SubscriptionStatus.ACTIVE, SubscriptionStatus.CANCELLED}
    ),
    SubscriptionStatus.PAUSED: frozenset(
        {SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL, SubscriptionStatus.EXPIRED}
    ),
    SubscriptionStatus.CANCELLED: frozenset({SubscriptionStatus.ACTIVE}),
    SubscriptionStatus.EXPIRED: frozenset({SubscriptionStatus.ACTIVE}),
}


class DomainError(ValueError):
    pass


def validate_transition(current: SubscriptionStatus, target: SubscriptionStatus) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise DomainError(f"transition from {current} to {target} is not allowed")


def validate_money(amount: Decimal, currency: str) -> tuple[Decimal, str]:
    normalized = currency.strip().upper()
    if amount < 0:
        raise DomainError("amount must not be negative")
    if len(normalized) != 3 or not normalized.isalpha():
        raise DomainError("currency must be a three-letter ISO 4217 code")
    return amount, normalized


def _add_months(anchor: date, months: int) -> date:
    month_index = anchor.year * 12 + anchor.month - 1 + months
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    return date(year, month, min(anchor.day, monthrange(year, month)[1]))


def next_occurrence(anchor: date, unit: IntervalUnit, count: int, occurrence: int = 1) -> date:
    if not 1 <= count <= 120 or occurrence < 1:
        raise DomainError("interval count and occurrence must be positive")
    factor = count * occurrence
    if unit == IntervalUnit.DAY:
        return anchor + timedelta(days=factor)
    if unit == IntervalUnit.WEEK:
        return anchor + timedelta(weeks=factor)
    if unit == IntervalUnit.MONTH:
        return _add_months(anchor, factor)
    return _add_months(anchor, 12 * factor)


@dataclass(frozen=True)
class BillingOccurrence:
    event_date: date
    amount: Decimal
    currency: str


def occurrences_through(
    anchor: date,
    unit: IntervalUnit,
    count: int,
    amount: Decimal,
    currency: str,
    start: date,
    end: date,
) -> list[BillingOccurrence]:
    amount, currency = validate_money(amount, currency)
    results: list[BillingOccurrence] = []
    current = anchor
    occurrence = 0
    while current <= end:
        if current >= start:
            results.append(BillingOccurrence(current, amount, currency))
        occurrence += 1
        current = next_occurrence(anchor, unit, count, occurrence)
    return results
