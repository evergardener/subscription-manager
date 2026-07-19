import json
import os
import subprocess
import sys
from pathlib import Path

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

SCRIPT = Path(__file__).parents[2] / "hermes" / "scripts" / "call_tool.py"


def run_tool(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = {
        **os.environ,
        "HERMES_SUBSCRIPTION_API_URL": "http://unused",
        "HERMES_SUBSCRIPTION_API_TOKEN": "secret",
    }
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        capture_output=True,
        check=False,
        encoding="utf-8",
        env=environment,
    )


def test_tool_runner_requires_confirmation_and_complete_arguments() -> None:
    unconfirmed = run_tool(
        "subscription_archive",
        "--arguments",
        '{"subscription_id":"00000000-0000-0000-0000-000000000001"}',
    )
    assert unconfirmed.returncode == 2
    assert (
        json.loads(unconfirmed.stdout)["error"]
        == "explicit confirmation is required for this write"
    )

    incomplete = run_tool("payment_record", "--arguments", "{}", "--confirm")
    assert incomplete.returncode == 2
    assert "missing required arguments" in json.loads(incomplete.stdout)["error"]

    missing_expiry = run_tool(
        "subscription_transition",
        "--arguments",
        '{"subscription_id":"00000000-0000-0000-0000-000000000001","expected_version":1,"target_status":"pending_cancel","reason":"requested"}',
        "--confirm",
    )
    assert missing_expiry.returncode == 2
    assert json.loads(missing_expiry.stdout)["error"] == (
        "service_expiry_date is required for pending_cancel"
    )


async def test_hermes_token_real_api_actor_scopes_and_header_spoofing(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    del db_session
    credentials = {"username": "admin", "password": "correct horse battery staple"}
    assert (await client.post("/api/v1/auth/bootstrap", json=credentials)).status_code == 201
    login = await client.post("/api/v1/auth/login", json=credentials)
    csrf = login.json()["csrf_token"]

    privileged = await client.post(
        "/api/v1/api-tokens",
        headers={"X-CSRF-Token": csrf},
        json={
            "name": "invalid",
            "actor_type": "hermes",
            "actor_id": "hermes-p5",
            "scopes": ["tokens:manage"],
        },
    )
    assert privileged.status_code == 422

    token_response = await client.post(
        "/api/v1/api-tokens",
        headers={"X-CSRF-Token": csrf},
        json={
            "name": "P5 Hermes",
            "actor_type": "hermes",
            "actor_id": "hermes-p5",
            "scopes": [
                "subscriptions:read",
                "subscriptions:write",
                "payments:write",
                "analytics:read",
                "audit:read",
            ],
        },
    )
    assert token_response.status_code == 201
    bearer = {
        "Authorization": f"Bearer {token_response.json()['token']}",
        "X-Actor-Type": "user",
        "X-Actor-Id": "forged-user",
        "Idempotency-Key": "p5-hermes-create",
    }
    created = await client.post(
        "/api/v1/subscriptions",
        headers=bearer,
        json={
            "name": "Hermes P5 API",
            "status": "active",
            "billing_plan": {
                "amount": "12.00",
                "currency": "USD",
                "interval_unit": "month",
                "interval_count": 1,
                "anchor_date": "2026-08-19",
                "next_billing_date": "2026-08-19",
                "auto_renew": True,
                "billing_mode": "fixed",
            },
        },
    )
    assert created.status_code == 201
    subscription_id = created.json()["id"]
    assert (
        await client.get(f"/api/v1/subscriptions/{subscription_id}", headers=bearer)
    ).status_code == 200
    assert (await client.get("/api/v1/analytics/summary", headers=bearer)).status_code == 200
    assert (await client.get("/api/v1/api-tokens", headers=bearer)).status_code == 403

    events = await client.get("/api/v1/events/upcoming?days=366", headers=bearer)
    billing_event = next(
        item
        for item in events.json()
        if item["subscription_id"] == subscription_id and item["event_type"] == "billing"
    )
    payment = await client.post(
        f"/api/v1/subscriptions/{subscription_id}/payments",
        headers={**bearer, "Idempotency-Key": "p5-hermes-payment"},
        json={
            "amount": "12.00",
            "currency": "USD",
            "paid_at": "2026-08-19T00:00:00Z",
            "billing_event_id": billing_event["id"],
            "advance_schedule": True,
            "source": "hermes",
        },
    )
    assert payment.status_code == 201
    advanced = await client.get(f"/api/v1/subscriptions/{subscription_id}", headers=bearer)
    assert advanced.json()["billing_plan"]["next_billing_date"] != "2026-08-19"

    transition = await client.post(
        f"/api/v1/subscriptions/{subscription_id}/status-transitions",
        headers=bearer,
        json={
            "target_status": "pending_cancel",
            "reason": "Hermes confirmed cancellation plan",
            "service_expiry_date": "2026-09-19",
            "expected_version": advanced.json()["version"],
        },
    )
    assert transition.status_code == 200
    assert transition.json()["status"] == "pending_cancel"

    audit = await client.get("/api/v1/audit-logs", headers=bearer)
    create_entry = next(item for item in audit.json()["items"] if item["action"] == "create")
    assert create_entry["actor_type"] == "hermes"
    assert create_entry["actor_id"] == "hermes-p5"
    payment_entry = next(
        item for item in audit.json()["items"] if item["action"] == "record_payment"
    )
    assert payment_entry["actor_type"] == "hermes"
    assert payment_entry["actor_id"] == "hermes-p5"
    transition_entry = next(
        item for item in audit.json()["items"] if item["action"] == "status_transition"
    )
    assert transition_entry["actor_type"] == "hermes"
    assert transition_entry["actor_id"] == "hermes-p5"
