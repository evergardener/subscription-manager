import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, cast
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import Actor, get_actor
from app.core.database import get_session
from app.core.request_context import request_id_context
from app.domain.billing import (
    DomainError,
    validate_money,
    validate_transition,
)
from app.domain.billing import (
    SubscriptionStatus as DomainStatus,
)
from app.models.tables import (
    AuditLog,
    BillingEvent,
    BillingPlan,
    Category,
    EventStatus,
    EventType,
    Payment,
    ReminderRule,
    ServiceDates,
    Subscription,
    SubscriptionStatus,
    Tag,
)
from app.services.business import (
    add_audit,
    add_idempotency,
    advance_plan,
    find_idempotency,
    generate_billing_events,
    generate_lifecycle_events,
    model_dict,
    replace_plan,
)
from app.services.exchange_rates import ExchangeRateResult, latest_cny_rates

router = APIRouter(prefix="/api/v1", tags=["business"])


class BillingPlanInput(BaseModel):
    amount: Decimal = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    interval_unit: Literal["day", "week", "month", "year"]
    interval_count: int = Field(ge=1, le=120)
    anchor_date: date
    next_billing_date: date | None = None
    auto_renew: bool = True
    billing_mode: Literal["fixed", "usage_based", "one_time", "free"] = "fixed"

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return validate_money(Decimal(0), value)[1]


class ServiceDatesInput(BaseModel):
    trial_end_date: date | None = None
    service_expiry_date: date | None = None
    cancellation_deadline: date | None = None
    contract_end_date: date | None = None


class SubscriptionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    vendor: str | None = Field(default=None, max_length=200)
    category_id: uuid.UUID | None = None
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE
    website: str | None = None
    logo_url: str | None = None
    description: str | None = None
    payment_method_description: str | None = Field(default=None, max_length=200)
    start_date: date | None = None
    billing_plan: BillingPlanInput
    service_dates: ServiceDatesInput | None = None

    @field_validator("website", "logo_url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        if value and urlparse(value).scheme not in {"http", "https"}:
            raise ValueError("URL must use http or https")
        return value


class SubscriptionPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    vendor: str | None = Field(default=None, max_length=200)
    category_id: uuid.UUID | None = None
    website: str | None = None
    logo_url: str | None = None
    description: str | None = None
    payment_method_description: str | None = Field(default=None, max_length=200)
    expected_version: int = Field(ge=1)
    billing_plan: BillingPlanInput | None = None
    service_dates: ServiceDatesInput | None = None


class TransitionInput(BaseModel):
    target_status: SubscriptionStatus
    reason: str = Field(min_length=1, max_length=500)
    service_expiry_date: date | None = None
    expected_version: int = Field(ge=1)


class PaymentInput(BaseModel):
    amount: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    paid_at: datetime
    tax_amount: Decimal = Field(default=Decimal(0), ge=0)
    source: Literal["manual", "hermes", "import"] = "manual"
    external_ref: str | None = Field(default=None, max_length=200)
    notes: str | None = None
    billing_event_id: uuid.UUID | None = None
    advance_schedule: bool = False


class NameInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    icon: str | None = None
    color: str | None = None
    sort_order: int = 0


class NamePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    icon: str | None = None
    color: str | None = None
    sort_order: int | None = None
    archived: bool | None = None
    expected_version: int = Field(ge=1)


class ReminderRuleInput(BaseModel):
    event_type: EventType
    offset_days: int = Field(ge=0, le=3650)
    channel: Literal["external"] = "external"
    enabled: bool = True


def subscription_json(item: Subscription, plan: BillingPlan | None = None) -> dict[str, Any]:
    result = model_dict(item)
    result["status"] = item.status.value
    if plan:
        result["billing_plan"] = model_dict(plan)
    return result


async def current_plan(session: AsyncSession, subscription_id: uuid.UUID) -> BillingPlan | None:
    return cast(
        BillingPlan | None,
        await session.scalar(
            select(BillingPlan).where(
                BillingPlan.subscription_id == subscription_id,
                BillingPlan.valid_to.is_(None),
            )
        ),
    )


@router.get("/subscriptions")
async def list_subscriptions(
    actor: Actor = Depends(get_actor),
    session: AsyncSession = Depends(get_session),
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    include_archived: bool = False,
    query: str | None = None,
) -> dict[str, Any]:
    actor.require("subscriptions:read")
    statement = select(Subscription, BillingPlan).outerjoin(
        BillingPlan,
        and_(
            BillingPlan.subscription_id == Subscription.id,
            BillingPlan.valid_to.is_(None),
        ),
    )
    count_statement = select(func.count()).select_from(Subscription)
    if not include_archived:
        statement = statement.where(Subscription.archived_at.is_(None))
        count_statement = count_statement.where(Subscription.archived_at.is_(None))
    if query:
        pattern = f"%{query.strip()}%"
        statement = statement.where(Subscription.name.ilike(pattern))
        count_statement = count_statement.where(Subscription.name.ilike(pattern))
    total = await session.scalar(count_statement) or 0
    items = (
        await session.execute(
            statement.order_by(Subscription.name).offset((page - 1) * page_size).limit(page_size)
        )
    ).all()
    return {
        "items": [subscription_json(item, plan) for item, plan in items],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.post("/subscriptions", status_code=201)
async def create_subscription(
    payload: SubscriptionCreate,
    request: Request,
    actor: Actor = Depends(get_actor),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    actor.require("subscriptions:write")
    key = request.headers.get("Idempotency-Key")
    try:
        cached = await find_idempotency(
            session,
            actor.actor_id,
            request.method,
            request.url.path,
            key,
            payload.model_dump(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if cached is not None:
        return cached
    item = Subscription(
        **payload.model_dump(exclude={"billing_plan", "service_dates", "name"}),
        name=payload.name.strip(),
    )
    session.add(item)
    await session.flush()
    plan = BillingPlan(subscription_id=item.id, **payload.billing_plan.model_dump())
    session.add(plan)
    await session.flush()
    await generate_billing_events(session, plan)
    result = subscription_json(item, plan)
    if payload.service_dates:
        dates = ServiceDates(subscription_id=item.id, **payload.service_dates.model_dump())
        session.add(dates)
        await session.flush()
        await generate_lifecycle_events(session, dates)
        await session.refresh(item)
        await session.refresh(dates)
        result["service_dates"] = model_dict(dates)
    add_audit(
        session,
        actor,
        "create",
        "subscription",
        item.id,
        request_id_context.get() or "unknown",
        None,
        model_dict(item),
        key,
    )
    add_idempotency(
        session,
        actor.actor_id,
        request.method,
        request.url.path,
        key,
        payload.model_dump(),
        result,
        201,
    )
    await session.commit()
    return result


@router.get("/subscriptions/{subscription_id}")
async def get_subscription(
    subscription_id: uuid.UUID,
    actor: Actor = Depends(get_actor),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    actor.require("subscriptions:read")
    item = await session.get(Subscription, subscription_id)
    if item is None:
        raise HTTPException(status_code=404, detail="subscription not found")
    result = subscription_json(item, await current_plan(session, item.id))
    dates = await session.get(ServiceDates, item.id)
    if dates:
        result["service_dates"] = model_dict(dates)
    return result


@router.patch("/subscriptions/{subscription_id}")
async def patch_subscription(
    subscription_id: uuid.UUID,
    payload: SubscriptionPatch,
    actor: Actor = Depends(get_actor),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    actor.require("subscriptions:write")
    item = await session.get(Subscription, subscription_id, with_for_update=True)
    if item is None:
        raise HTTPException(status_code=404, detail="subscription not found")
    if item.version != payload.expected_version:
        raise HTTPException(status_code=409, detail={"current_version": item.version})
    plan = await current_plan(session, item.id)
    dates = await session.get(ServiceDates, item.id)
    before = {
        "subscription": model_dict(item),
        "billing_plan": model_dict(plan) if plan else None,
        "service_dates": model_dict(dates) if dates else None,
    }
    changes = payload.model_dump(
        exclude_unset=True, exclude={"expected_version", "billing_plan", "service_dates"}
    )
    for key, value in changes.items():
        setattr(item, key, value.strip() if isinstance(value, str) else value)
    item.version += 1
    if payload.billing_plan and plan:
        now = datetime.now(UTC)
        new_plan = BillingPlan(
            subscription_id=item.id, **payload.billing_plan.model_dump(), valid_from=now
        )
        await replace_plan(session, plan, new_plan, now)
        plan = new_plan
        await session.flush()
        await session.refresh(item)
        await session.refresh(plan)
    if payload.service_dates:
        if dates is None:
            dates = ServiceDates(subscription_id=item.id)
            session.add(dates)
        for key, value in payload.service_dates.model_dump().items():
            setattr(dates, key, value)
        await session.flush()
        await generate_lifecycle_events(session, dates)
        await session.refresh(item)
        await session.refresh(dates)
    add_audit(
        session,
        actor,
        "update",
        "subscription",
        item.id,
        request_id_context.get() or "unknown",
        before,
        {
            "subscription": model_dict(item),
            "billing_plan": model_dict(plan) if plan else None,
            "service_dates": model_dict(dates) if dates else None,
        },
    )
    result = subscription_json(item, plan)
    if payload.service_dates:
        result["service_dates"] = model_dict(dates)
    await session.commit()
    return result


@router.post("/subscriptions/{subscription_id}/status-transitions")
async def transition_subscription(
    subscription_id: uuid.UUID,
    payload: TransitionInput,
    actor: Actor = Depends(get_actor),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    actor.require("subscriptions:write")
    item = await session.get(Subscription, subscription_id, with_for_update=True)
    if item is None:
        raise HTTPException(status_code=404, detail="subscription not found")
    if item.version != payload.expected_version:
        raise HTTPException(status_code=409, detail={"current_version": item.version})
    try:
        validate_transition(
            DomainStatus(item.status.value), DomainStatus(payload.target_status.value)
        )
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    before = model_dict(item)
    plan = await current_plan(session, item.id)
    plan_snapshot = model_dict(plan) if plan else None
    if payload.target_status == SubscriptionStatus.PENDING_CANCEL:
        if payload.service_expiry_date is None:
            raise HTTPException(
                status_code=422, detail="pending_cancel requires service_expiry_date"
            )
        dates = await session.get(ServiceDates, item.id)
        if dates is None:
            dates = ServiceDates(subscription_id=item.id)
            session.add(dates)
        dates.service_expiry_date = payload.service_expiry_date
        await session.flush()
        await generate_lifecycle_events(session, dates)
        if plan:
            plan.auto_renew = False
            if plan_snapshot:
                plan_snapshot["auto_renew"] = False
        future = (
            await session.scalars(
                select(BillingEvent).where(
                    BillingEvent.subscription_id == item.id,
                    BillingEvent.event_type == EventType.BILLING,
                    BillingEvent.event_date > payload.service_expiry_date,
                    BillingEvent.status == EventStatus.PLANNED,
                )
            )
        ).all()
        for event in future:
            event.status = EventStatus.CANCELLED
    elif (
        item.status == SubscriptionStatus.PENDING_CANCEL
        and payload.target_status == SubscriptionStatus.ACTIVE
    ):
        if plan:
            plan.auto_renew = True
            if plan_snapshot:
                plan_snapshot["auto_renew"] = True
            cancelled = (
                await session.scalars(
                    select(BillingEvent).where(
                        BillingEvent.billing_plan_id == plan.id,
                        BillingEvent.status == EventStatus.CANCELLED,
                        BillingEvent.event_date >= date.today(),
                    )
                )
            ).all()
            for event in cancelled:
                event.status = EventStatus.PLANNED
            await generate_billing_events(session, plan)
    item.status = payload.target_status
    item.version += 1
    add_audit(
        session,
        actor,
        "status_transition",
        "subscription",
        item.id,
        request_id_context.get() or "unknown",
        before,
        model_dict(item),
    )
    result = subscription_json(item)
    if plan_snapshot:
        result["billing_plan"] = plan_snapshot
    await session.commit()
    return result


async def set_archive(
    subscription_id: uuid.UUID, archived: bool, actor: Actor, session: AsyncSession
) -> dict[str, Any]:
    actor.require("subscriptions:write")
    item = await session.get(Subscription, subscription_id, with_for_update=True)
    if item is None:
        raise HTTPException(status_code=404, detail="subscription not found")
    plan = await current_plan(session, item.id)
    before = model_dict(item)
    item.archived_at = datetime.now(UTC) if archived else None
    item.version += 1
    add_audit(
        session,
        actor,
        "archive" if archived else "restore",
        "subscription",
        item.id,
        request_id_context.get() or "unknown",
        before,
        model_dict(item),
    )
    result = subscription_json(item, plan)
    await session.commit()
    return result


@router.post("/subscriptions/{subscription_id}/archive")
async def archive_subscription(
    subscription_id: uuid.UUID,
    actor: Actor = Depends(get_actor),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await set_archive(subscription_id, True, actor, session)


@router.post("/subscriptions/{subscription_id}/restore")
async def restore_subscription(
    subscription_id: uuid.UUID,
    actor: Actor = Depends(get_actor),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await set_archive(subscription_id, False, actor, session)


@router.get("/subscriptions/{subscription_id}/payments")
async def list_payments(
    subscription_id: uuid.UUID,
    actor: Actor = Depends(get_actor),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    actor.require("subscriptions:read")
    items = (
        await session.scalars(
            select(Payment)
            .where(Payment.subscription_id == subscription_id)
            .order_by(Payment.paid_at.desc())
        )
    ).all()
    return [model_dict(item) for item in items]


@router.post("/subscriptions/{subscription_id}/payments", status_code=201)
async def record_payment(
    subscription_id: uuid.UUID,
    payload: PaymentInput,
    request: Request,
    actor: Actor = Depends(get_actor),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    actor.require("payments:write")
    key = request.headers.get("Idempotency-Key")
    try:
        cached = await find_idempotency(
            session,
            actor.actor_id,
            request.method,
            request.url.path,
            key,
            payload.model_dump(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if cached is not None:
        return cached
    if payload.tax_amount > payload.amount:
        raise HTTPException(status_code=422, detail="tax amount cannot exceed amount")
    item = await session.get(Subscription, subscription_id)
    if item is None:
        raise HTTPException(status_code=404, detail="subscription not found")
    event = (
        await session.get(BillingEvent, payload.billing_event_id, with_for_update=True)
        if payload.billing_event_id
        else None
    )
    plan = await current_plan(session, subscription_id)
    if payload.advance_schedule and (
        event is None
        or plan is None
        or event.billing_plan_id != plan.id
        or event.status != EventStatus.PLANNED
    ):
        raise HTTPException(
            status_code=422,
            detail="schedule advancement requires the current planned billing event",
        )
    payment = Payment(
        subscription_id=subscription_id, **payload.model_dump(exclude={"advance_schedule"})
    )
    session.add(payment)
    await session.flush()
    if event:
        event.status = EventStatus.RECONCILED
        event.version += 1
    if payload.advance_schedule and event and plan:
        plan.next_billing_date = advance_plan(plan, event.event_date)
        plan.version += 1
        await generate_billing_events(session, plan)
    result = model_dict(payment)
    add_audit(
        session,
        actor,
        "record_payment",
        "payment",
        payment.id,
        request_id_context.get() or "unknown",
        None,
        model_dict(payment),
        key,
    )
    add_idempotency(
        session,
        actor.actor_id,
        request.method,
        request.url.path,
        key,
        payload.model_dump(),
        result,
        201,
    )
    await session.commit()
    return result


@router.get("/events/upcoming")
async def upcoming_events(
    days: Annotated[int, Query(ge=1, le=366)] = 30,
    actor: Actor = Depends(get_actor),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    actor.require("subscriptions:read")
    end = date.today().fromordinal(date.today().toordinal() + days)
    items = (
        await session.scalars(
            select(BillingEvent)
            .where(
                BillingEvent.event_date.between(date.today(), end),
                BillingEvent.status == EventStatus.PLANNED,
            )
            .order_by(BillingEvent.event_date)
        )
    ).all()
    return [
        {**model_dict(item), "event_type": item.event_type.value, "status": item.status.value}
        for item in items
    ]


@router.get("/analytics/summary")
async def analytics_summary(
    actor: Actor = Depends(get_actor), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    actor.require("analytics:read")
    expected_rows = (
        await session.execute(
            select(BillingEvent.currency, func.sum(BillingEvent.amount))
            .where(BillingEvent.status == EventStatus.PLANNED, BillingEvent.amount.is_not(None))
            .group_by(BillingEvent.currency)
        )
    ).all()
    actual_rows = (
        await session.execute(
            select(Payment.currency, func.sum(Payment.amount)).group_by(Payment.currency)
        )
    ).all()
    expected_vendors = (
        await session.execute(
            select(Subscription.vendor, BillingEvent.currency, func.sum(BillingEvent.amount))
            .join(BillingEvent, BillingEvent.subscription_id == Subscription.id)
            .where(BillingEvent.status == EventStatus.PLANNED, BillingEvent.amount.is_not(None))
            .group_by(Subscription.vendor, BillingEvent.currency)
        )
    ).all()
    actual_vendors = (
        await session.execute(
            select(Subscription.vendor, Payment.currency, func.sum(Payment.amount))
            .join(Payment, Payment.subscription_id == Subscription.id)
            .group_by(Subscription.vendor, Payment.currency)
        )
    ).all()
    expected_categories = (
        await session.execute(
            select(Category.name, BillingEvent.currency, func.sum(BillingEvent.amount))
            .select_from(Subscription)
            .outerjoin(Category, Category.id == Subscription.category_id)
            .join(BillingEvent, BillingEvent.subscription_id == Subscription.id)
            .where(BillingEvent.status == EventStatus.PLANNED, BillingEvent.amount.is_not(None))
            .group_by(Category.name, BillingEvent.currency)
        )
    ).all()
    actual_categories = (
        await session.execute(
            select(Category.name, Payment.currency, func.sum(Payment.amount))
            .select_from(Subscription)
            .outerjoin(Category, Category.id == Subscription.category_id)
            .join(Payment, Payment.subscription_id == Subscription.id)
            .group_by(Category.name, Payment.currency)
        )
    ).all()

    def breakdown(
        expected: list[tuple[str | None, str, Decimal]],
        actual: list[tuple[str | None, str, Decimal]],
        fallback: str,
    ) -> list[dict[str, str]]:
        values: dict[tuple[str, str], dict[str, str]] = {}
        for label, currency, amount in expected:
            key = (label or fallback, currency)
            values[key] = {
                "label": key[0],
                "currency": currency,
                "expected": str(amount),
                "actual": "0",
            }
        for label, currency, amount in actual:
            key = (label or fallback, currency)
            values.setdefault(
                key,
                {"label": key[0], "currency": currency, "expected": "0", "actual": "0"},
            )["actual"] = str(amount)
        return sorted(values.values(), key=lambda item: (item["currency"], item["label"]))

    return {
        "expected": {currency: str(amount) for currency, amount in expected_rows},
        "actual": {currency: str(amount) for currency, amount in actual_rows},
        "by_vendor": breakdown(
            [
                (label, currency, amount)
                for label, currency, amount in expected_vendors
                if currency is not None and amount is not None
            ],
            [(label, currency, amount) for label, currency, amount in actual_vendors],
            "未填写供应商",
        ),
        "by_category": breakdown(
            [
                (label, currency, amount)
                for label, currency, amount in expected_categories
                if currency is not None and amount is not None
            ],
            [(label, currency, amount) for label, currency, amount in actual_categories],
            "未分类",
        ),
    }


@router.get("/exchange-rates/latest")
async def exchange_rates_latest(actor: Actor = Depends(get_actor)) -> ExchangeRateResult:
    actor.require("analytics:read")
    try:
        return await latest_cny_rates()
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail="exchange rates are temporarily unavailable"
        ) from exc


@router.get("/audit-logs")
async def audit_logs(
    actor: Actor = Depends(get_actor),
    session: AsyncSession = Depends(get_session),
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, Any]:
    actor.require("audit:read")
    total = await session.scalar(select(func.count()).select_from(AuditLog)) or 0
    items = (
        await session.scalars(
            select(AuditLog)
            .order_by(AuditLog.occurred_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return {
        "items": [{**model_dict(item), "actor_type": item.actor_type.value} for item in items],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


async def list_names(
    model: type[Category] | type[Tag], actor: Actor, session: AsyncSession
) -> list[dict[str, Any]]:
    actor.require("subscriptions:read")
    return [
        model_dict(item)
        for item in (
            await session.scalars(
                select(model).where(model.archived_at.is_(None)).order_by(model.name)
            )
        ).all()
    ]


@router.get("/categories")
async def list_categories(
    actor: Actor = Depends(get_actor), session: AsyncSession = Depends(get_session)
) -> list[dict[str, Any]]:
    return await list_names(Category, actor, session)


@router.post("/categories", status_code=201)
async def create_category(
    payload: NameInput,
    actor: Actor = Depends(get_actor),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    actor.require("subscriptions:write")
    item = Category(
        name=payload.name.strip(),
        normalized_name=payload.name.strip().casefold(),
        icon=payload.icon,
        sort_order=payload.sort_order,
    )
    session.add(item)
    await session.flush()
    add_audit(
        session,
        actor,
        "create",
        "category",
        item.id,
        request_id_context.get() or "unknown",
        None,
        model_dict(item),
    )
    await session.commit()
    return model_dict(item)


async def patch_name_resource(
    model: type[Category] | type[Tag],
    resource_id: uuid.UUID,
    payload: NamePatch,
    actor: Actor,
    session: AsyncSession,
) -> dict[str, Any]:
    actor.require("subscriptions:write")
    item = cast(
        Category | Tag,
        await session.get(model, resource_id, with_for_update=True),
    )
    if item is None:
        raise HTTPException(status_code=404, detail="resource not found")
    if item.version != payload.expected_version:
        raise HTTPException(status_code=409, detail={"current_version": item.version})
    before = model_dict(item)
    changes = payload.model_dump(exclude_unset=True, exclude={"expected_version", "archived"})
    for key, value in changes.items():
        if hasattr(item, key):
            setattr(item, key, value.strip() if isinstance(value, str) else value)
    if payload.name is not None:
        item.normalized_name = payload.name.strip().casefold()
    if payload.archived is not None:
        item.archived_at = datetime.now(UTC) if payload.archived else None
    item.version += 1
    result = model_dict(item)
    add_audit(
        session,
        actor,
        "update",
        model.__tablename__,
        item.id,
        request_id_context.get() or "unknown",
        before,
        result,
    )
    await session.commit()
    return result


@router.patch("/categories/{resource_id}")
async def patch_category(
    resource_id: uuid.UUID,
    payload: NamePatch,
    actor: Actor = Depends(get_actor),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await patch_name_resource(Category, resource_id, payload, actor, session)


@router.get("/tags")
async def list_tags(
    actor: Actor = Depends(get_actor), session: AsyncSession = Depends(get_session)
) -> list[dict[str, Any]]:
    return await list_names(Tag, actor, session)


@router.post("/tags", status_code=201)
async def create_tag(
    payload: NameInput,
    actor: Actor = Depends(get_actor),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    actor.require("subscriptions:write")
    item = Tag(
        name=payload.name.strip(),
        normalized_name=payload.name.strip().casefold(),
        color=payload.color,
    )
    session.add(item)
    await session.flush()
    add_audit(
        session,
        actor,
        "create",
        "tag",
        item.id,
        request_id_context.get() or "unknown",
        None,
        model_dict(item),
    )
    await session.commit()
    return model_dict(item)


@router.patch("/tags/{resource_id}")
async def patch_tag(
    resource_id: uuid.UUID,
    payload: NamePatch,
    actor: Actor = Depends(get_actor),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await patch_name_resource(Tag, resource_id, payload, actor, session)


@router.get("/subscriptions/{subscription_id}/reminder-rules")
async def get_reminder_rules(
    subscription_id: uuid.UUID,
    actor: Actor = Depends(get_actor),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    actor.require("subscriptions:read")
    items = (
        await session.scalars(
            select(ReminderRule).where(ReminderRule.subscription_id == subscription_id)
        )
    ).all()
    return [{**model_dict(item), "event_type": item.event_type.value} for item in items]


@router.put("/subscriptions/{subscription_id}/reminder-rules")
async def put_reminder_rules(
    subscription_id: uuid.UUID,
    payload: list[ReminderRuleInput],
    actor: Actor = Depends(get_actor),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    actor.require("subscriptions:write")
    existing = (
        await session.scalars(
            select(ReminderRule).where(ReminderRule.subscription_id == subscription_id)
        )
    ).all()
    before = {str(item.id): model_dict(item) for item in existing}
    by_key = {(item.event_type, item.offset_days, item.channel): item for item in existing}
    records: list[ReminderRule] = []
    selected: set[uuid.UUID] = set()
    for rule in payload:
        key = (rule.event_type, rule.offset_days, rule.channel)
        record = by_key.get(key)
        if record is None:
            record = ReminderRule(subscription_id=subscription_id, **rule.model_dump())
            session.add(record)
            await session.flush()
        else:
            record.enabled = rule.enabled
            record.version += 1
        selected.add(record.id)
        records.append(record)
    for item in existing:
        if item.id not in selected and item.enabled:
            item.enabled = False
            item.version += 1
    add_audit(
        session,
        actor,
        "replace_rules",
        "subscription_reminder_rules",
        subscription_id,
        request_id_context.get() or "unknown",
        before,
        {str(item.id): model_dict(item) for item in records},
    )
    await session.commit()
    return [{**model_dict(item), "event_type": item.event_type.value} for item in records]
