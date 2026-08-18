"""
TasaVzla — FastAPI application entry point.

Endpoints:
  GET /rate/usd   → latest USD/VES official rate
  GET /rate/eur   → latest EUR/VES official rate
  GET /health     → liveness probe

All rate endpoints always respond instantly from the DB cache.
A background job keeps the cache fresh; the /rate/* endpoints
never block on an external HTTP call.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.config import settings
from app.crud import get_latest_rate, upsert_rate
from app.database import AsyncSessionLocal, create_tables, get_db
from app.fetcher import fetch_rate
from app.models import ExchangeRate
from app.schemas import HealthResponse, RateResponse
from app.scheduler import scheduler, setup_scheduler

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

_CURRENCIES = ["USD", "EUR"]


# ── Background refresh ─────────────────────────────────────────────────────


async def _refresh_currency(currency: str) -> None:
    """Fetch a fresh rate and persist it to the cache DB."""
    result = await fetch_rate(currency)
    if result is None:
        logger.warning("Both sources failed for %s; cache not updated", currency)
        return

    async with AsyncSessionLocal() as db:
        row = await upsert_rate(
            db,
            currency=currency,
            rate=result.rate,
            source=result.source,
            rate_date=result.rate_date,
        )
    logger.info(
        "Cache updated: %s = %.6f (source=%s, date=%s)",
        currency,
        row.rate,
        row.source,
        row.rate_date,
    )


async def refresh_all_rates() -> None:
    """Refresh USD and EUR concurrently."""
    await asyncio.gather(*(_refresh_currency(c) for c in _CURRENCIES))


# ── Lifespan ───────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting TasaVzla API v%s", __version__)
    await create_tables()

    setup_scheduler(refresh_all_rates)
    scheduler.start()

    # Initial fetch so the cache is never empty on a cold start
    logger.info("Running initial rate fetch...")
    await refresh_all_rates()

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")


# ── App ────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="TasaVzla",
    description=(
        "Exposes the official BCV (Banco Central de Venezuela) exchange rates "
        "for USD/VES and EUR/VES. Rates are cached in the database and refreshed "
        "automatically on Venezuelan business hours."
    ),
    version=__version__,
    lifespan=lifespan,
)


# ── Helpers ────────────────────────────────────────────────────────────────


def _row_to_response(row: ExchangeRate, stale: bool = False) -> RateResponse:
    return RateResponse(
        currency=row.currency,
        rate=float(row.rate),
        source=row.source if not stale else "cached_stale",  # type: ignore[arg-type]
        rate_date=row.rate_date,
        fetched_at=row.fetched_at,
        stale=stale,
    )


async def _get_rate_response(currency: str, db: AsyncSession) -> RateResponse:
    row = await get_latest_rate(db, currency)
    if row is None:
        raise HTTPException(
            status_code=503,
            detail=(
                f"No cached rate for {currency} yet. "
                "The scheduler will populate it shortly."
            ),
        )
    return _row_to_response(row)


# ── Routes ─────────────────────────────────────────────────────────────────


@app.get(
    "/rate/usd",
    response_model=RateResponse,
    summary="Latest USD/VES official rate",
    tags=["rates"],
)
async def get_usd_rate(db: AsyncSession = Depends(get_db)) -> RateResponse:
    """
    Returns the latest cached USD/VES official rate published by the BCV.

    - **rate**: bolivares per 1 USD
    - **source**: where the value was obtained
    - **stale**: true if both BCV and fallback were unreachable at the last refresh
    """
    return await _get_rate_response("USD", db)


@app.get(
    "/rate/eur",
    response_model=RateResponse,
    summary="Latest EUR/VES official rate",
    tags=["rates"],
)
async def get_eur_rate(db: AsyncSession = Depends(get_db)) -> RateResponse:
    """
    Returns the latest cached EUR/VES official rate published by the BCV.

    - **rate**: bolivares per 1 EUR
    - **source**: where the value was obtained
    - **stale**: true if both BCV and fallback were unreachable at the last refresh
    """
    return await _get_rate_response("EUR", db)


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness probe",
    tags=["ops"],
)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")
