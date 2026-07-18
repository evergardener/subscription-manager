import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import Actor, get_actor, hash_password, new_secret, sha256, verify_password
from app.core.config import get_settings
from app.core.database import get_session
from app.models.tables import ActorType, ApiToken, Session, User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
token_router = APIRouter(prefix="/api/v1/api-tokens", tags=["auth"])


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=12, max_length=500)


class TokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    actor_type: ActorType = ActorType.HERMES
    actor_id: str = Field(min_length=1, max_length=200)
    scopes: list[str] = Field(min_length=1)
    expires_at: datetime | None = None


@router.post("/bootstrap", status_code=201)
async def bootstrap(
    payload: Credentials, session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    if await session.scalar(select(func.count()).select_from(User)):
        raise HTTPException(status_code=409, detail="administrator already exists")
    user = User(
        username=payload.username.strip(),
        normalized_username=payload.username.strip().casefold(),
        password_hash=hash_password(payload.password),
    )
    session.add(user)
    await session.commit()
    return {"id": str(user.id), "username": user.username}


@router.post("/login")
async def login(
    payload: Credentials, response: Response, session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    user = await session.scalar(
        select(User).where(User.normalized_username == payload.username.strip().casefold())
    )
    if user is None or not verify_password(user.password_hash, payload.password):
        raise HTTPException(status_code=401, detail="invalid credentials")
    settings = get_settings()
    now = datetime.now(UTC)
    csrf = new_secret()
    record = Session(
        user_id=user.id,
        csrf_hash=sha256(csrf),
        expires_at=now + timedelta(hours=settings.session_absolute_hours),
        idle_expires_at=now + timedelta(minutes=settings.session_idle_minutes),
        last_seen_at=now,
    )
    session.add(record)
    await session.commit()
    response.set_cookie(
        "hermes_session",
        str(record.id),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=settings.session_absolute_hours * 3600,
    )
    return {"username": user.username, "csrf_token": csrf}


@router.get("/session")
async def current_session(
    actor: Actor = Depends(get_actor), session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    if actor.session_id is None:
        raise HTTPException(status_code=401, detail="browser session required")
    record = await session.get(Session, actor.session_id, with_for_update=True)
    if record is None or record.revoked_at is not None:
        raise HTTPException(status_code=401, detail="session is no longer active")
    csrf = new_secret()
    record.csrf_hash = sha256(csrf)
    await session.commit()
    return {
        "actor_type": actor.actor_type.value,
        "actor_id": actor.actor_id,
        "csrf_token": csrf,
    }


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    actor: Actor = Depends(get_actor),
    session: AsyncSession = Depends(get_session),
) -> Response:
    if actor.session_id:
        record = await session.get(Session, actor.session_id)
        if record:
            record.revoked_at = datetime.now(UTC)
            await session.commit()
    response.delete_cookie("hermes_session")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@token_router.get("")
async def list_tokens(
    actor: Actor = Depends(get_actor), session: AsyncSession = Depends(get_session)
) -> list[dict[str, object]]:
    actor.require("tokens:manage")
    records = (await session.scalars(select(ApiToken).order_by(ApiToken.created_at))).all()
    return [
        {
            "id": str(item.id),
            "name": item.name,
            "actor_type": item.actor_type.value,
            "actor_id": item.actor_id,
            "scopes": item.scopes,
            "expires_at": item.expires_at,
            "revoked_at": item.revoked_at,
        }
        for item in records
    ]


@token_router.post("", status_code=201)
async def create_token(
    payload: TokenCreate,
    actor: Actor = Depends(get_actor),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    actor.require("tokens:manage")
    raw = new_secret("hsm_")
    record = ApiToken(
        name=payload.name.strip(),
        actor_type=payload.actor_type,
        actor_id=payload.actor_id,
        token_hash=sha256(raw),
        scopes=payload.scopes,
        expires_at=payload.expires_at,
    )
    session.add(record)
    await session.commit()
    return {"id": str(record.id), "token": raw, "scopes": record.scopes}


@token_router.delete("/{token_id}", status_code=204)
async def revoke_token(
    token_id: uuid.UUID,
    actor: Actor = Depends(get_actor),
    session: AsyncSession = Depends(get_session),
) -> None:
    actor.require("tokens:manage")
    record = await session.get(ApiToken, token_id)
    if record is None:
        raise HTTPException(status_code=404, detail="token not found")
    record.revoked_at = datetime.now(UTC)
    await session.commit()
