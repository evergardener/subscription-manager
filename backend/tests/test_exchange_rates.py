from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.services import exchange_rates
from app.services.exchange_rates import ExchangeRateResult, latest_cny_rates, parse_ecb_rates


def test_parse_ecb_rates_converts_euro_quotes_to_cny() -> None:
    payload = """<?xml version="1.0" encoding="UTF-8"?>
    <Envelope><Cube><Cube time="2026-07-17">
      <Cube currency="USD" rate="1.1435" />
      <Cube currency="CNY" rate="7.7293" />
    </Cube></Cube></Envelope>"""

    result = parse_ecb_rates(payload)

    assert result["date"] == "2026-07-17"
    assert result["rates"]["CNY"] == "1"
    assert Decimal(result["rates"]["USD"]).quantize(Decimal("0.0001")) == Decimal("6.7593")


def test_parse_ecb_rates_rejects_incomplete_payloads() -> None:
    with pytest.raises(ValueError, match="rate date"):
        parse_ecb_rates("<Envelope><Cube /></Envelope>")
    with pytest.raises(ValueError, match="CNY"):
        parse_ecb_rates(
            '<Envelope><Cube time="2026-07-17"><Cube currency="USD" rate="1" /></Cube></Envelope>'
        )


async def test_latest_rates_uses_fresh_cache() -> None:
    cached: ExchangeRateResult = {
        "base": "CNY",
        "date": "2026-07-17",
        "source": "ECB",
        "source_url": "https://example.test",
        "rates": {"CNY": "1"},
    }
    exchange_rates._cache = (datetime.now(UTC), cached)
    try:
        assert await latest_cny_rates() is cached
    finally:
        exchange_rates._cache = None
