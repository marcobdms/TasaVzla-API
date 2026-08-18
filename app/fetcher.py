"""
Fetcher orchestrator.

Implements the priority chain:
  1. BCV direct scraper  (primary)
  2. dolarapi.com        (fallback)
  3. Cached DB value     (stale — handled in main.py)

Returns a dataclass with the rate, its source label, and the rate date.
"""

import logging
from dataclasses import dataclass
from datetime import date

from app.fallback import fetch_fallback
from app.scraper import scrape_bcv

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    rate: float
    source: str  # 'bcv_direct' | 'dolarapi_fallback'
    rate_date: date


async def fetch_rate(currency: str) -> FetchResult | None:
    """
    Attempt to fetch a fresh rate using the priority chain.

    Returns None if both sources fail (caller should serve stale cache).
    """
    # ── 1. BCV direct ──────────────────────────────────────────────────────
    try:
        rate, rate_date = await scrape_bcv(currency)
        return FetchResult(rate=rate, source="bcv_direct", rate_date=rate_date)
    except Exception as exc:
        logger.warning(
            "BCV scraper failed for %s after all retries: %s — trying fallback",
            currency,
            exc,
        )

    # ── 2. dolarapi.com fallback ────────────────────────────────────────────
    try:
        rate, rate_date = await fetch_fallback(currency)
        return FetchResult(rate=rate, source="dolarapi_fallback", rate_date=rate_date)
    except Exception as exc:
        logger.error(
            "Fallback also failed for %s: %s — will serve stale cache",
            currency,
            exc,
        )

    return None
