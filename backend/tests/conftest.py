import os
from collections.abc import AsyncIterator

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session_factory
from app.main import app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client


@pytest.fixture(scope="session")
def migrated_database() -> None:
    if "DATABASE_URL" not in os.environ:
        pytest.skip("DATABASE_URL is required for PostgreSQL integration tests")
    config = Config("alembic.ini")
    command.upgrade(config, "head")


@pytest.fixture
async def db_session(migrated_database: None) -> AsyncIterator[AsyncSession]:
    del migrated_database
    async with get_session_factory()() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE reminder_deliveries, reminder_rules, payments, billing_events, "
                "billing_plans, service_dates, subscription_tags, subscriptions, categories, tags, "
                "audit_logs, idempotency_records, sessions, api_tokens, users CASCADE"
            )
        )
        await session.commit()
        yield session
