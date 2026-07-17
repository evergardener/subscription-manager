import json
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from httpx import AsyncClient

import app.api.health as health_module
from app.core.logging import JsonFormatter

AsyncProbe = Callable[[], Coroutine[Any, Any, None]]


async def test_live_returns_request_id(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health/live", headers={"X-Request-ID": "test-request"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"] == "test-request"


async def test_ready_returns_ok_when_database_is_available(
    client: AsyncClient,
    monkeypatch: Any,
) -> None:
    async def healthy_probe() -> None:
        return None

    monkeypatch.setattr(health_module, "check_database", healthy_probe)
    response = await client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_returns_503_without_error_details(
    client: AsyncClient,
    monkeypatch: Any,
) -> None:
    async def failing_probe() -> None:
        raise OSError("database secret must not leak")

    monkeypatch.setattr(health_module, "check_database", failing_probe)
    response = await client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}
    assert "secret" not in response.text


def test_json_formatter_has_required_context_fields() -> None:
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "hello", (), None)

    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "hello"
    assert {"request_id", "actor", "entity_id"} <= payload.keys()
