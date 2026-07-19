from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.middleware import RateLimitMiddleware, RequestIdMiddleware, SecurityHeadersMiddleware


async def test_security_headers_cover_success_errors_and_forwarded_https() -> None:
    application = FastAPI()
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(RequestIdMiddleware)

    @application.get("/ok")
    async def ok() -> dict[str, bool]:
        return {"ok": True}

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://testserver"
    ) as client:
        response = await client.get("/ok", headers={"X-Forwarded-Proto": "https"})
        missing = await client.get("/missing")

    for item in (response, missing):
        assert item.headers["x-content-type-options"] == "nosniff"
        assert item.headers["x-frame-options"] == "DENY"
        assert item.headers["referrer-policy"] == "no-referrer"
        assert "frame-ancestors 'none'" in item.headers["content-security-policy"]
        assert item.headers["x-request-id"]
    assert response.headers["strict-transport-security"].startswith("max-age=31536000")


async def test_rate_limit_returns_structured_429_and_excludes_health() -> None:
    application = FastAPI()
    application.add_middleware(RateLimitMiddleware, api_limit=2, login_limit=2, window_seconds=60)
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(RequestIdMiddleware)

    @application.get("/api/v1/example")
    async def example() -> dict[str, bool]:
        return {"ok": True}

    @application.get("/api/v1/health/ready")
    async def ready() -> dict[str, bool]:
        return {"ok": True}

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://testserver"
    ) as client:
        assert (await client.get("/api/v1/example")).status_code == 200
        assert (await client.get("/api/v1/example")).status_code == 200
        limited = await client.get("/api/v1/example")
        assert (await client.get("/api/v1/health/ready")).status_code == 200

    assert limited.status_code == 429
    assert limited.json()["code"] == "rate_limited"
    assert limited.json()["request_id"]
    assert limited.headers["retry-after"]
    assert limited.headers["x-content-type-options"] == "nosniff"
