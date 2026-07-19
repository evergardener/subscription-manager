from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import Actor, hash_password
from app.models.tables import Session, User
from app.services.business import add_audit


async def replace_password(
    session: AsyncSession,
    user: User,
    new_password: str,
    actor: Actor,
    request_id: str,
    action: str,
) -> None:
    changed_at = datetime.now(UTC)
    before = {"username": user.username, "password_changed_at": user.password_changed_at}
    user.password_hash = hash_password(new_password)
    user.password_changed_at = changed_at
    user.version += 1
    await session.execute(
        update(Session)
        .where(Session.user_id == user.id, Session.revoked_at.is_(None))
        .values(revoked_at=changed_at)
    )
    add_audit(
        session,
        actor,
        action,
        "user",
        user.id,
        request_id,
        before,
        {"username": user.username, "password_changed_at": changed_at},
    )
    await session.commit()
