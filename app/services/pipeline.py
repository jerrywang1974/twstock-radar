from __future__ import annotations

import datetime as dt
from typing import Optional, Union

from sqlalchemy.orm import Session

from app.notify import send_digest
from app.rules.engine import format_digest, persist_hits, scan_trust_rules
from app.services.ai_analysis import analyze_hits, format_ai_section, insights_as_dict
from app.services.ingest import ingest_date


DateLike = Union[str, dt.date, dt.datetime]


def run_daily_pipeline(
    db: Session,
    trade_date: Optional[DateLike] = None,
    notify: bool = True,
) -> dict:
    job = ingest_date(db, trade_date)
    day = job.trade_date
    hits = []
    alerts = []
    insights = []

    if job.status in {"success", "empty"}:
        hits = scan_trust_rules(db, day)
        if hits:
            persist_hits(db, hits)
            insights = analyze_hits(db, hits)
        subject, body = format_digest(hits, day)
        body = body + format_ai_section(insights)
        if notify:
            alerts = send_digest(db, day, subject, body)
    else:
        subject = f"[twstock-radar] ingest failed {day.isoformat()}"
        body = job.message
        if notify:
            alerts = send_digest(db, day, subject, body)

    return {
        "job": {
            "id": job.id,
            "trade_date": day.isoformat(),
            "status": job.status,
            "twse_rows": job.twse_rows,
            "tpex_rows": job.tpex_rows,
            "message": job.message,
        },
        "hits": len(hits),
        "ai_insights": insights_as_dict(insights),
        "alerts": [
            {"id": a.id, "channel": a.channel, "status": a.status, "error": a.error}
            for a in alerts
        ],
    }
