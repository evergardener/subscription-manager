import uuid
from datetime import date

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import BillingEvent, EventStatus, EventType, ReminderRule


async def test_session_csrf_scoped_token_revocation_and_actor_headers(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    credentials = {"username": "admin", "password": "correct horse battery staple"}
    response = await client.post("/api/v1/auth/bootstrap", json=credentials)
    assert response.status_code == 201
    login = await client.post("/api/v1/auth/login", json=credentials)
    assert login.status_code == 200
    csrf = login.json()["csrf_token"]

    restored_session = await client.get("/api/v1/auth/session")
    assert restored_session.status_code == 200
    assert restored_session.json()["csrf_token"] != csrf
    csrf = restored_session.json()["csrf_token"]

    rejected = await client.post("/api/v1/categories", json={"name": "Cloud"})
    assert rejected.status_code == 403
    assert rejected.json()["code"] == "http_403"

    headers = {
        "X-CSRF-Token": csrf,
        "X-Actor-Type": "hermes",
        "X-Actor-Id": "forged",
    }
    created = await client.post(
        "/api/v1/subscriptions",
        headers={**headers, "Idempotency-Key": "api-integration-create"},
        json={
            "name": "API Integration",
            "billing_plan": {
                "amount": "10.000000",
                "currency": "USD",
                "interval_unit": "month",
                "interval_count": 1,
                "anchor_date": "2026-07-31",
                "next_billing_date": "2026-07-31",
                "auto_renew": True,
                "billing_mode": "fixed",
            },
        },
    )
    assert created.status_code == 201
    duplicate = await client.post(
        "/api/v1/subscriptions",
        headers={**headers, "Idempotency-Key": "api-integration-create"},
        json={
            "name": "API Integration",
            "billing_plan": {
                "amount": "10.000000",
                "currency": "USD",
                "interval_unit": "month",
                "interval_count": 1,
                "anchor_date": "2026-07-31",
                "next_billing_date": "2026-07-31",
                "auto_renew": True,
                "billing_mode": "fixed",
            },
        },
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["id"] == created.json()["id"]
    subscriptions = await client.get("/api/v1/subscriptions")
    assert subscriptions.status_code == 200
    assert subscriptions.json()["items"][0]["billing_plan"]["currency"] == "USD"
    assert subscriptions.json()["items"][0]["billing_plan"]["amount"] == "10.000000"
    analytics = await client.get("/api/v1/analytics/summary")
    assert analytics.status_code == 200
    assert analytics.json()["by_vendor"][0]["currency"] == "USD"
    assert analytics.json()["by_vendor"][0]["label"] == "未填写供应商"

    transition = await client.post(
        f"/api/v1/subscriptions/{created.json()['id']}/status-transitions",
        headers={"X-CSRF-Token": csrf},
        json={
            "target_status": "pending_cancel",
            "reason": "cancelled with vendor",
            "service_expiry_date": "2026-08-15",
            "expected_version": created.json()["version"],
        },
    )
    assert transition.status_code == 200
    assert transition.json()["status"] == "pending_cancel"
    stale_transition = await client.post(
        f"/api/v1/subscriptions/{created.json()['id']}/status-transitions",
        headers={"X-CSRF-Token": csrf},
        json={
            "target_status": "active",
            "reason": "stale browser",
            "expected_version": created.json()["version"],
        },
    )
    assert stale_transition.status_code == 409
    assert stale_transition.json()["details"]["current_version"] == transition.json()["version"]
    await db_session.rollback()
    cancelled = list(
        await db_session.scalars(
            select(BillingEvent).where(BillingEvent.status == EventStatus.CANCELLED)
        )
    )
    assert cancelled
    restored = await client.post(
        f"/api/v1/subscriptions/{created.json()['id']}/status-transitions",
        headers={"X-CSRF-Token": csrf},
        json={
            "target_status": "active",
            "reason": "cancellation withdrawn",
            "expected_version": transition.json()["version"],
        },
    )
    assert restored.status_code == 200
    await db_session.rollback()
    assert not list(
        await db_session.scalars(
            select(BillingEvent).where(BillingEvent.status == EventStatus.CANCELLED)
        )
    )

    patched = await client.patch(
        f"/api/v1/subscriptions/{created.json()['id']}",
        headers={"X-CSRF-Token": csrf},
        json={
            "expected_version": restored.json()["version"],
            "service_dates": {"service_expiry_date": "2026-09-15"},
        },
    )
    assert patched.status_code == 200
    await db_session.rollback()
    old_expiry = await db_session.scalar(
        select(BillingEvent).where(
            BillingEvent.subscription_id == created.json()["id"],
            BillingEvent.event_type == EventType.EXPIRY,
            BillingEvent.event_date == date(2026, 8, 15),
        )
    )
    assert old_expiry is not None
    assert old_expiry.status == EventStatus.SUPERSEDED

    current_plan = patched.json()["billing_plan"]
    non_renewing = await client.patch(
        f"/api/v1/subscriptions/{created.json()['id']}",
        headers={"X-CSRF-Token": csrf},
        json={
            "expected_version": patched.json()["version"],
            "billing_plan": {
                key: value
                for key, value in current_plan.items()
                if key
                in {
                    "amount",
                    "currency",
                    "interval_unit",
                    "interval_count",
                    "anchor_date",
                    "next_billing_date",
                    "billing_mode",
                }
            }
            | {"auto_renew": False},
        },
    )
    assert non_renewing.status_code == 200
    assert non_renewing.json()["billing_plan"]["auto_renew"] is False
    audit_after_plan = await client.get("/api/v1/audit-logs?page_size=100")
    plan_change = next(
        entry
        for entry in audit_after_plan.json()["items"]
        if entry["action"] == "update"
        and entry["after_json"].get("billing_plan", {}).get("auto_renew") is False
    )
    assert plan_change["before_json"]["billing_plan"]["auto_renew"] is True
    assert plan_change["after_json"]["service_dates"]["service_expiry_date"] == "2026-09-15"
    await db_session.rollback()
    assert not list(
        await db_session.scalars(
            select(BillingEvent).where(
                BillingEvent.billing_plan_id == non_renewing.json()["billing_plan"]["id"],
                BillingEvent.status == EventStatus.PLANNED,
            )
        )
    )

    rules_url = f"/api/v1/subscriptions/{created.json()['id']}/reminder-rules"
    rules = await client.put(
        rules_url,
        headers={"X-CSRF-Token": csrf},
        json=[{"event_type": "expiry", "offset_days": 7, "channel": "external"}],
    )
    assert rules.status_code == 200
    rule_id = rules.json()[0]["id"]
    disabled = await client.put(rules_url, headers={"X-CSRF-Token": csrf}, json=[])
    assert disabled.status_code == 200
    await db_session.rollback()
    retained_rule = await db_session.get(ReminderRule, uuid.UUID(rule_id))
    assert retained_rule is not None
    assert not retained_rule.enabled

    archived = await client.post(
        f"/api/v1/subscriptions/{created.json()['id']}/archive",
        headers={"X-CSRF-Token": csrf},
    )
    assert archived.status_code == 200
    assert archived.json()["archived_at"] is not None
    restored_archive = await client.post(
        f"/api/v1/subscriptions/{created.json()['id']}/restore",
        headers={"X-CSRF-Token": csrf},
    )
    assert restored_archive.status_code == 200
    assert restored_archive.json()["archived_at"] is None

    audit = await client.get("/api/v1/audit-logs")
    assert audit.status_code == 200
    assert audit.json()["items"][0]["actor_type"] == "user"
    assert audit.json()["items"][0]["actor_id"] != "forged"

    token_response = await client.post(
        "/api/v1/api-tokens",
        headers={"X-CSRF-Token": csrf},
        json={
            "name": "read only",
            "actor_type": "hermes",
            "actor_id": "hermes-test",
            "scopes": ["subscriptions:read"],
        },
    )
    assert token_response.status_code == 201
    token = token_response.json()["token"]
    token_id = token_response.json()["id"]
    bearer = {"Authorization": f"Bearer {token}"}
    assert (await client.get("/api/v1/subscriptions", headers=bearer)).status_code == 200
    assert (await client.get("/api/v1/audit-logs", headers=bearer)).status_code == 403

    revoked = await client.delete(f"/api/v1/api-tokens/{token_id}", headers={"X-CSRF-Token": csrf})
    assert revoked.status_code == 204
    assert (await client.get("/api/v1/subscriptions", headers=bearer)).status_code == 401


async def test_openapi_exposes_p1_to_p3_contracts(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    required = {
        "/api/v1/auth/login",
        "/api/v1/auth/change-password",
        "/api/v1/subscriptions",
        "/api/v1/subscriptions/{subscription_id}/payments",
        "/api/v1/events/upcoming",
        "/api/v1/analytics/summary",
        "/api/v1/audit-logs",
        "/api/v1/reminders/scan",
        "/api/v1/reminders/claim",
        "/api/v1/reminders/deliveries/{delivery_id}/ack",
        "/api/v1/reminders/deliveries/{delivery_id}/fail",
    }
    assert required <= paths.keys()
