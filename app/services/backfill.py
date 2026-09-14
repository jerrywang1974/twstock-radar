from __future__ import annotations

import datetime as dt
import time
from typing import Optional, Union

from sqlalchemy.orm import Session

from app.config import get_settings
from app.services.ingest import ingest_date
from app.services.pipeline import run_daily_pipeline


DateLike = Union[str, dt.date, dt.datetime]


def _as_date(value: DateLike) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    text = str(value).strip()
    if "-" in text:
        return dt.datetime.strptime(text[:10], "%Y-%m-%d").date()
    return dt.datetime.strptime(text, "%Y%m%d").date()


def backfill_range(
    db: Session,
    start: DateLike,
    end: Optional[DateLike] = None,
    *,
    notify: bool = False,
    run_rules: bool = True,
    sleep_seconds: float | None = None,
) -> dict:
    """Ingest (and optionally scan) each calendar day from start..end inclusive.

    Non-trading days typically become ingest status ``empty`` and are skipped for rules.
    """
    settings = get_settings()
    start_day = _as_date(start)
    end_day = _as_date(end) if end is not None else dt.date.today()
    if end_day < start_day:
        raise ValueError("end date must be >= start date")

    pause = (
        settings.backfill_sleep_seconds
        if sleep_seconds is None
        else float(sleep_seconds)
    )
    results = []
    day = start_day
    while day <= end_day:
        if run_rules:
            item = run_daily_pipeline(db, trade_date=day, notify=notify)
        else:
            job = ingest_date(db, day)
            item = {
                "job": {
                    "id": job.id,
                    "trade_date": day.isoformat(),
                    "status": job.status,
                    "twse_rows": job.twse_rows,
                    "tpex_rows": job.tpex_rows,
                    "message": job.message,
                },
                "hits": 0,
                "alerts": [],
            }
        results.append(item)
        day += dt.timedelta(days=1)
        if day <= end_day and pause > 0:
            time.sleep(pause)

    success = sum(1 for r in results if r["job"]["status"] == "success")
    empty = sum(1 for r in results if r["job"]["status"] == "empty")
    failed = sum(1 for r in results if r["job"]["status"] == "failed")
    return {
        "start": start_day.isoformat(),
        "end": end_day.isoformat(),
        "days": len(results),
        "success": success,
        "empty": empty,
        "failed": failed,
        "results": results,
    }
