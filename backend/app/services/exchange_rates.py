import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TypedDict
from xml.etree import ElementTree

import httpx

ECB_DAILY_RATES_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"


class ExchangeRateResult(TypedDict):
    base: str
    date: str
    source: str
    source_url: str
    rates: dict[str, str]


_cache: tuple[datetime, ExchangeRateResult] | None = None
_lock = asyncio.Lock()


def parse_ecb_rates(xml: str) -> ExchangeRateResult:
    root = ElementTree.fromstring(xml)
    dated_cube = next((item for item in root.iter() if "time" in item.attrib), None)
    if dated_cube is None:
        raise ValueError("ECB response does not contain a rate date")
    rates = {"EUR": Decimal("1")}
    rates.update(
        {
            item.attrib["currency"]: Decimal(item.attrib["rate"])
            for item in dated_cube
            if "currency" in item.attrib and "rate" in item.attrib
        }
    )
    if "CNY" not in rates:
        raise ValueError("ECB response does not contain CNY")
    cny_per_eur = rates["CNY"]
    return {
        "base": "CNY",
        "date": dated_cube.attrib["time"],
        "source": "European Central Bank",
        "source_url": ECB_DAILY_RATES_URL,
        "rates": {currency: str(cny_per_eur / rate) for currency, rate in rates.items()},
    }


async def latest_cny_rates() -> ExchangeRateResult:
    global _cache
    now = datetime.now(UTC)
    if _cache is not None and now - _cache[0] < timedelta(hours=6):
        return _cache[1]
    async with _lock:
        if _cache is not None and now - _cache[0] < timedelta(hours=6):
            return _cache[1]
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(ECB_DAILY_RATES_URL)
            response.raise_for_status()
        result = parse_ecb_rates(response.text)
        _cache = (now, result)
        return result
