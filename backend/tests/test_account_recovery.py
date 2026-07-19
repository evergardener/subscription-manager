from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cli import reset_admin_password
from app.models.tables import AuditLog, Session


async def test_change_and_offline_reset_revoke_sessions_and_audit(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    credentials = {"username": "admin", "password": "correct horse battery staple"}
    assert (await client.post("/api/v1/auth/bootstrap", json=credentials)).status_code == 201
    first_login = await client.post("/api/v1/auth/login", json=credentials)
    second_login = await client.post("/api/v1/auth/login", json=credentials)
    assert first_login.status_code == second_login.status_code == 200
    csrf = second_login.json()["csrf_token"]

    incorrect = await client.post(
        "/api/v1/auth/change-password",
        headers={"X-CSRF-Token": csrf},
        json={"current_password": "incorrect", "new_password": "new secure password one"},
    )
    assert incorrect.status_code == 401

    changed = await client.post(
        "/api/v1/auth/change-password",
        headers={"X-CSRF-Token": csrf},
        json={
            "current_password": credentials["password"],
            "new_password": "new secure password one",
        },
    )
    assert changed.status_code == 204
    sessions = list(await db_session.scalars(select(Session)))
    assert len(sessions) == 2
    assert all(item.revoked_at is not None for item in sessions)
    assert (await client.post("/api/v1/auth/login", json=credentials)).status_code == 401
    new_credentials = {"username": "admin", "password": "new secure password one"}
    assert (await client.post("/api/v1/auth/login", json=new_credentials)).status_code == 200

    await reset_admin_password("admin", "offline reset password two")
    assert (await client.get("/api/v1/auth/session")).status_code == 401
    reset_credentials = {"username": "admin", "password": "offline reset password two"}
    assert (await client.post("/api/v1/auth/login", json=reset_credentials)).status_code == 200

    entries = list(
        await db_session.scalars(
            select(AuditLog).where(AuditLog.action.in_(["password_change", "password_reset"]))
        )
    )
    assert {item.action for item in entries} == {"password_change", "password_reset"}
    assert next(item for item in entries if item.action == "password_change").actor_type == "user"
    reset_entry = next(item for item in entries if item.action == "password_reset")
    assert reset_entry.actor_type == "system"
    assert reset_entry.actor_id == "local-password-reset"
    assert all(
        "password_hash" not in str(item.before_json) + str(item.after_json) for item in entries
    )
