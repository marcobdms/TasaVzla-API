from datetime import date, datetime, timezone

from sqlalchemy import desc, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ExchangeRate


async def upsert_rate(
    db: AsyncSession,
    *,
    currency: str,
    rate: float,
    source: str,
    rate_date: date,
    fetched_at: datetime | None = None,
) -> ExchangeRate:
    """
    Insert a new rate or update an existing one for the same (currency, rate_date).
    Uses PostgreSQL's ON CONFLICT DO UPDATE so it's a single round-trip.
    """
    if fetched_at is None:
        fetched_at = datetime.now(tz=timezone.utc)

    stmt = (
        insert(ExchangeRate)
        .values(
            currency=currency.upper(),
            rate=rate,
            source=source,
            rate_date=rate_date,
            fetched_at=fetched_at,
        )
        .on_conflict_do_update(
            constraint="uq_currency_rate_date",
            set_={
                "rate": rate,
                "source": source,
                "fetched_at": fetched_at,
            },
        )
        .returning(ExchangeRate)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.scalar_one()


async def get_latest_rate(db: AsyncSession, currency: str) -> ExchangeRate | None:
    """Return the most recently fetched rate row for the given currency."""
    stmt = (
        select(ExchangeRate)
        .where(ExchangeRate.currency == currency.upper())
        .order_by(desc(ExchangeRate.fetched_at))
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
