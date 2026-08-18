"""
Fallback data source: ve.dolarapi.com

Used when the BCV scraper fails after all retries.
dolarapi.com is an open-source, community-maintained project
that independently tracks BCV rates.

Endpoints used:
  USD: GET https://ve.dolarapi.com/v1/dolares/oficial
  EUR: GET https://ve.dolarapi.com/v1/euros           (filter fuente=oficial)
"""

import logging
from datetime import date, datetime, timezone

import httpx

logger = logging.getLogger(__name__)

_BASE = "https://ve.dolarapi.com/v1"
_TIMEOUT = 10.0

# Maps currency code → (url, response_type)
# 'object'  → response is a single JSON object
# 'array'   → response is a JSON array; we filter by fuente=oficial
_ENDPOINTS: dict[str, tuple[str, str]] = {
    "USD": (f"{_BASE}/dolares/oficial", "object"),
    "EUR": (f"{_BASE}/euros", "array"),
}


def _parse_date(date_str: str) -> date:
    """Parse ISO-8601 date string from dolarapi into a date object."""
    return datetime.fromisoformat(date_str).date()


async def fetch_fallback(currency: str) -> tuple[float, date]:
    """
    Fetch the official BCV rate from ve.dolarapi.com.

    Returns:
        (rate, rate_date)

    Raises:
        ValueError if the currency is unsupported or the rate is unavailable.
        httpx.HTTPError on network issues.
    """
    currency = currency.upper()
    if currency not in _ENDPOINTS:
        raise ValueError(f"Unsupported currency for fallback: {currency}")

    url, response_type = _ENDPOINTS[currency]
    logger.info("Fetching fallback for %s from %s", currency, url)

    async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

    if response_type == "array":
        # Find the entry with fuente=oficial
        entry = next(
            (item for item in data if item.get("fuente") == "oficial"), None
        )
        if entry is None:
            raise ValueError(f"No 'oficial' entry found in dolarapi response for {currency}")
    else:
        entry = data

    rate = entry.get("promedio")
    if rate is None:
        raise ValueError(f"Null 'promedio' in dolarapi response for {currency}")

    rate_date_str = entry.get("fechaActualizacion", "")
    try:
        rate_date = _parse_date(rate_date_str)
    except (ValueError, TypeError):
        # If date parse fails, fallback to today in VET
        rate_date = datetime.now(tz=timezone.utc).astimezone(
            __import__("zoneinfo").ZoneInfo("America/Caracas")
        ).date()

    logger.info("Fallback OK: %s = %.6f (from dolarapi.com)", currency, rate)
    return float(rate), rate_date
