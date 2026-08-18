"""
APScheduler setup.

Runs refresh_all_rates() at 15:00, 17:00 and 19:00 VET (Mon–Fri).
In UTC those are 19:00, 21:00, 23:00.

The BCV typically publishes around 14:00–16:00 VET.  Three runs give us
redundancy: if the BCV is slow or we catch it mid-update, the next run
will pick it up within 2 hours without pounding the server every minute.
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings

logger = logging.getLogger(__name__)

_CURRENCIES = ["USD", "EUR"]

# Module-level scheduler instance shared with main.py
scheduler = AsyncIOScheduler(timezone="UTC")


def _make_trigger() -> CronTrigger:
    hours_str = ",".join(str(h) for h in settings.scheduler_hours_utc)
    return CronTrigger(
        day_of_week="mon-fri",
        hour=hours_str,
        minute=0,
        timezone="UTC",
    )


def setup_scheduler(refresh_callback) -> None:
    """
    Register the rate-refresh job.

    Args:
        refresh_callback: async callable that refreshes all rates; must be
                          a coroutine function (defined in main.py to avoid
                          circular imports with the DB session factory).
    """
    scheduler.add_job(
        refresh_callback,
        trigger=_make_trigger(),
        id="refresh_rates",
        replace_existing=True,
        misfire_grace_time=300,  # allow up to 5 min late if the server was busy
    )
    logger.info(
        "Scheduler configured: refresh at UTC hours %s, Mon–Fri",
        settings.scheduler_hours_utc,
    )
