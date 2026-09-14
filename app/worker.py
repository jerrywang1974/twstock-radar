from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.services.pipeline import run_daily_pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("twstock-radar.worker")


def _job() -> None:
    settings = get_settings()
    logger.info("starting scheduled pipeline at %s", datetime.now(ZoneInfo(settings.timezone)))
    db = SessionLocal()
    try:
        result = run_daily_pipeline(db, notify=True)
        logger.info("pipeline result: %s", result)
    except Exception:
        logger.exception("pipeline failed")
    finally:
        db.close()


def main() -> None:
    settings = get_settings()
    init_db()
    scheduler = BlockingScheduler(timezone=settings.timezone)

    # Default after-close retries on weekdays.
    for hhmm in settings.ingest_retry_times.split(","):
        hour, minute = hhmm.strip().split(":")
        scheduler.add_job(
            _job,
            CronTrigger(
                day_of_week="mon-fri",
                hour=int(hour),
                minute=int(minute),
                timezone=settings.timezone,
            ),
            id=f"ingest-{hhmm.strip()}",
            replace_existing=True,
        )
        logger.info("scheduled weekday job at %s %s", hhmm.strip(), settings.timezone)

    scheduler.start()


if __name__ == "__main__":
    main()
