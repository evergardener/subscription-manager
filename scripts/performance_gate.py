import argparse
import json
import math
import time
from urllib.request import Request, urlopen


def percentile_95(samples: list[float]) -> float:
    ordered = sorted(samples)
    return ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)]


def measure(base_url: str, token: str, path: str, samples: int) -> tuple[float, int]:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    size = 0
    for _ in range(3):
        with urlopen(Request(base_url + path, headers=headers), timeout=10) as response:
            response.read()
    timings: list[float] = []
    for _ in range(samples):
        started = time.perf_counter()
        with urlopen(Request(base_url + path, headers=headers), timeout=10) as response:
            body = response.read()
        timings.append((time.perf_counter() - started) * 1000)
        size = len(body)
    return percentile_95(timings), size


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--samples", type=int, default=20)
    arguments = parser.parse_args()
    if arguments.samples < 20:
        parser.error("at least 20 samples are required")
    checks = {
        "subscription_list": ("/api/v1/subscriptions?page_size=100", 500),
        "subscription_search": (
            "/api/v1/subscriptions?query=Performance%20Subscription%2009999&page_size=100",
            500,
        ),
        "analytics_summary": ("/api/v1/analytics/summary", 500),
        "upcoming_events_30d": ("/api/v1/events/upcoming?days=30", 1000),
    }
    results: dict[str, dict[str, float | int]] = {}
    failed = False
    for name, (path, limit) in checks.items():
        p95, size = measure(
            arguments.base_url.rstrip("/"), arguments.token, path, arguments.samples
        )
        results[name] = {
            "p95_ms": round(p95, 2),
            "limit_ms": limit,
            "response_bytes": size,
        }
        failed = failed or p95 >= limit
    print(
        json.dumps(
            {"subscriptions": 10000, "samples": arguments.samples, "results": results}
        )
    )
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
