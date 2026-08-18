"""
BCV direct scraper.

Scrapes the sidebar exchange-rate widget on bcv.org.ve.
The widget uses static IDs (#dolar, #euro) that have been stable
across multiple Drupal theme updates.

Retry strategy: tenacity with exponential backoff so transient
BCV outages don't surface to callers.
"""

import logging
from datetime import date, datetime, timezone

import httpx
from bs4 import BeautifulSoup
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings

logger = logging.getLogger(__name__)

_BCV_URL = "https://www.bcv.org.ve/"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-VE,es;q=0.9,en;q=0.8",
}

# Currency id → HTML element id on bcv.org.ve
_CURRENCY_IDS: dict[str, str] = {
    "USD": "dolar",
    "EUR": "euro",
}


def _parse_rate(html: str, currency: str) -> float:
    """Extract and parse a rate value from the BCV HTML."""
    soup = BeautifulSoup(html, "lxml")
    element_id = _CURRENCY_IDS[currency.upper()]
    container = soup.find("div", id=element_id)
    if container is None:
        raise ValueError(f"Could not find div#'{element_id}' in BCV HTML")
    strong = container.find("strong")
    if strong is None:
        raise ValueError(f"No <strong> tag inside div#'{element_id}'")
    # BCV uses Venezuelan locale: "773,3125" → need to normalize
    raw = strong.get_text(strip=True).replace(".", "").replace(",", ".")
    return float(raw)


@retry(
    retry=retry_if_exception_type((httpx.HTTPError, ValueError, Exception)),
    stop=stop_after_attempt(settings.bcv_retries),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)
async def _fetch_bcv_html() -> str:
    """Fetch the BCV homepage HTML with retries."""
    async with httpx.AsyncClient(
        timeout=settings.bcv_timeout,
        verify=False,  # BCV SSL certs are often misconfigured
        follow_redirects=True,
    ) as client:
        response = await client.get(_BCV_URL, headers=_HEADERS)
        response.raise_for_status()
        return response.text


async def scrape_bcv(currency: str) -> tuple[float, date]:
    """
    Scrape the BCV website for the given currency rate.

    Returns:
        (rate, rate_date) where rate_date is today in Venezuela (VET = UTC-4).

    Raises:
        Exception if all retry attempts are exhausted.
    """
    logger.info("Scraping BCV for %s...", currency)
    html = await _fetch_bcv_html()
    rate = _parse_rate(html, currency)
    # BCV publishes the rate for today in VET timezone
    rate_date = datetime.now(tz=timezone.utc).astimezone(
        __import__("zoneinfo").ZoneInfo("America/Caracas")
    ).date()
    logger.info("BCV scrape OK: %s = %.6f", currency, rate)
    return rate, rate_date
