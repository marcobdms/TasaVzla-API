from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


SourceType = Literal["bcv_direct", "dolarapi_fallback", "cached_stale"]


class RateResponse(BaseModel):
    """Response body for /rate/usd and /rate/eur."""

    currency: str = Field(examples=["USD"])
    rate: float = Field(examples=[773.3125])
    source: SourceType = Field(
        description=(
            "bcv_direct → scraped from bcv.org.ve; "
            "dolarapi_fallback → taken from ve.dolarapi.com; "
            "cached_stale → BCV and fallback both failed, returning last known value"
        )
    )
    rate_date: date = Field(description="Date the BCV considers this rate valid")
    fetched_at: datetime = Field(description="When this value was stored in our cache")
    stale: bool = Field(
        default=False,
        description="True when both primary and fallback sources failed; value may be outdated",
    )


class HealthResponse(BaseModel):
    status: str = "ok"
