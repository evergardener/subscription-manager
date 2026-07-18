import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session
from app.models.tables import ActorType, ApiToken, Session, User

password_hasher = PasswordHasher()


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("password must contain at least 12 characters")
    return password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def new_secret(prefix: str = "") -> str:
    return prefix + secrets.token_urlsafe(32)


@dataclass(frozen=True)
class Actor:
    actor_type: ActorType
    actor_id: str
    scopes: frozenset[str]
    session_id: uuid.UUID | None = None

    def require(self, scope: str) -> None:
        if "*" not in self.scopes and scope not in self.scopes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient scope")


async def _session_actor(request: Request, session: AsyncSession, session_id: str) -> Actor | None:
    try:
        parsed = uuid.UUID(session_id)
    except ValueError:
        return None
    now = datetime.now(UTC)
    record = await session.get(Session, parsed)
    if (
        record is None
        or record.revoked_at is not None
        or record.expires_at <= now
        or record.idle_expires_at <= now
    ):
        return None
    user = await session.get(User, record.user_id)
    if user is None or user.password_changed_at > record.last_seen_at:
        return None
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf = request.headers.get("X-CSRF-Token")
        if not csrf or not secrets.compare_digest(record.csrf_hash, sha256(csrf)):
            raise HTTPException(status_code=403, detail="invalid CSRF token")
    settings = get_settings()
    record.last_seen_at = now
    record.idle_expires_at = now + timedelta(minutes=settings.session_idle_minutes)
    await session.commit()
    return Actor(ActorType.USER, str(user.id), frozenset({"*"}), record.id)


async def get_actor(
    request: Request,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> Actor:
    if authorization and authorization.startswith("Bearer "):
        raw = authorization[7:]
        record = await session.scalar(select(ApiToken).where(ApiToken.token_hash == sha256(raw)))
        now = datetime.now(UTC)
        if (
            record is None
            or record.revoked_at is not None
            or (record.expires_at is not None and record.expires_at <= now)
        ):
            raise HTTPException(status_code=401, detail="invalid API token")
        record.last_used_at = now
        await session.commit()
        return Actor(record.actor_type, record.actor_id, frozenset(record.scopes))
    cookie = request.cookies.get("hermes_session")
    if cookie and (actor := await _session_actor(request, session, cookie)):
        return actor
    raise HTTPException(status_code=401, detail="authentication required")
