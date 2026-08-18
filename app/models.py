from datetime import date, datetime

from sqlalchemy import Date, DateTime, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ExchangeRate(Base):
    """
    Stores the latest known exchange rate per currency per day.
    The UNIQUE constraint on (currency, rate_date) lets us upsert
    without duplicates while keeping the full history.
    """

    __tablename__ = "exchange_rates"

    id: Mapped[int] = mapped_column(primary_key=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)  # 'USD' | 'EUR'
    rate: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    # Date the BCV considers this rate valid (usually "today" in Venezuela)
    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    # When our scraper actually fetched & stored this value
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("currency", "rate_date", name="uq_currency_rate_date"),
    )

    def __repr__(self) -> str:
        return f"<ExchangeRate {self.currency} {self.rate} @ {self.rate_date}>"
