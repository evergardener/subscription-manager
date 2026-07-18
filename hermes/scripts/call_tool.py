#!/usr/bin/env python3
"""Call the Subscription Manager API using the P5 Hermes tool contract."""

from __future__ import annotations

import argparse
import json
import os
import uuid
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

CONFIRMATION_REQUIRED = {
    "subscription_create",
    "subscription_update",
    "subscription_archive",
    "payment_record",
}
ALLOWED_ARGUMENTS = {
    "subscription_search": {"query", "include_archived"},
    "subscription_get": {"subscription_id"},
    "subscription_create": {
        "name",
        "vendor",
        "status",
        "billing_plan",
        "service_dates",
    },
    "subscription_update": {
        "subscription_id",
        "expected_version",
        "name",
        "vendor",
        "billing_plan",
        "service_dates",
    },
    "subscription_archive": {"subscription_id"},
    "payment_record": {
        "subscription_id",
        "amount",
        "currency",
        "paid_at",
        "tax_amount",
        "notes",
        "billing_event_id",
        "advance_schedule",
    },
    "upcoming_events": {"days", "event_types"},
    "analytics_summary": {"currencies"},
}
REQUIRED_ARGUMENTS = {
    "subscription_get": {"subscription_id"},
    "subscription_create": {"name", "status", "billing_plan"},
    "subscription_update": {"subscription_id", "expected_version"},
    "subscription_archive": {"subscription_id"},
    "payment_record": {
        "subscription_id",
        "amount",
        "currency",
        "paid_at",
        "advance_schedule",
    },
}


def fail(message: str, code: int = 2) -> None:
    print(json.dumps({"ok": False, "error": message}, ensure_ascii=False))
    raise SystemExit(code)


def endpoint(tool: str, arguments: dict[str, Any]) -> tuple[str, str, dict[str, Any] | None]:
    subscription_id = arguments.pop("subscription_id", None)
    if tool == "subscription_search":
        return "GET", f"/api/v1/subscriptions?{urlencode(arguments)}", None
    if tool == "subscription_get":
        return "GET", f"/api/v1/subscriptions/{subscription_id}", None
    if tool == "subscription_create":
        return "POST", "/api/v1/subscriptions", arguments
    if tool == "subscription_update":
        return "PATCH", f"/api/v1/subscriptions/{subscription_id}", arguments
    if tool == "subscription_archive":
        return "POST", f"/api/v1/subscriptions/{subscription_id}/archive", None
    if tool == "payment_record":
        return (
            "POST",
            f"/api/v1/subscriptions/{subscription_id}/payments",
            {**arguments, "source": "hermes"},
        )
    if tool == "upcoming_events":
        event_types = arguments.pop("event_types", None)
        path = f"/api/v1/events/upcoming?{urlencode(arguments)}"
        return "GET", path, {"event_types": event_types} if event_types else None
    if tool == "analytics_summary":
        return (
            "GET",
            "/api/v1/analytics/summary",
            {"currencies": arguments.get("currencies")} if arguments.get("currencies") else None,
        )
    fail(f"unsupported tool: {tool}")


def filter_result(tool: str, result: Any, client_filter: dict[str, Any] | None) -> Any:
    if not client_filter:
        return result
    if tool == "upcoming_events":
        allowed = set(client_filter["event_types"])
        return [item for item in result if item.get("event_type") in allowed]
    if tool == "analytics_summary":
        allowed = set(client_filter["currencies"])
        return {
            **result,
            "expected": {k: v for k, v in result.get("expected", {}).items() if k in allowed},
            "actual": {k: v for k, v in result.get("actual", {}).items() if k in allowed},
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("tool", choices=sorted(ALLOWED_ARGUMENTS))
    parser.add_argument("--arguments", default="{}")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    try:
        arguments = json.loads(args.arguments)
    except json.JSONDecodeError as exc:
        fail(f"arguments must be valid JSON: {exc.msg}")
    if not isinstance(arguments, dict):
        fail("arguments must be a JSON object")
    unknown = set(arguments) - ALLOWED_ARGUMENTS[args.tool]
    if unknown:
        fail(f"unsupported arguments: {', '.join(sorted(unknown))}")
    missing = REQUIRED_ARGUMENTS.get(args.tool, set()) - set(arguments)
    if missing:
        fail(f"missing required arguments: {', '.join(sorted(missing))}")
    if args.tool in CONFIRMATION_REQUIRED and not args.confirm:
        fail("explicit confirmation is required for this write")
    base_url = os.getenv("HERMES_SUBSCRIPTION_API_URL", "").rstrip("/")
    token = os.getenv("HERMES_SUBSCRIPTION_API_TOKEN", "")
    if not base_url or not token:
        fail("HERMES_SUBSCRIPTION_API_URL and HERMES_SUBSCRIPTION_API_TOKEN are required")
    method, path, body_or_filter = endpoint(args.tool, dict(arguments))
    body = body_or_filter if method not in {"GET"} else None
    client_filter = body_or_filter if method == "GET" else None
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if method in {"POST", "PATCH"}:
        headers["Content-Type"] = "application/json"
    if args.tool in {"subscription_create", "payment_record"}:
        headers["Idempotency-Key"] = str(uuid.uuid4())
    request = Request(
        base_url + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(request, timeout=15) as response:
            result = json.load(response)
            output = {
                "ok": True,
                "status": response.status,
                "request_id": response.headers.get("X-Request-ID"),
                "result": filter_result(args.tool, result, client_filter),
            }
    except HTTPError as exc:
        try:
            error = json.load(exc)
        except (json.JSONDecodeError, UnicodeDecodeError):
            error = {"code": f"http_{exc.code}", "message": "non-JSON service error"}
        output = {
            "ok": False,
            "status": exc.code,
            "request_id": exc.headers.get("X-Request-ID"),
            "error": error,
        }
    except (URLError, TimeoutError) as exc:
        fail(
            f"service unavailable: {exc.reason if isinstance(exc, URLError) else exc}",
            1,
        )
    print(json.dumps(output, ensure_ascii=False, separators=(",", ":")))
    if not output["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
