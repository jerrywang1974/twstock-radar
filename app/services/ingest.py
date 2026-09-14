from __future__ import annotations

import datetime as dt
from typing import Optional, Union

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import IngestJob, InstitutionalDaily
from twstock.institutional import fetch as fetch_institutional


DateLike = Union[str, dt.date, dt.datetime]


def _as_date(value: Optional[DateLike] = None) -> dt.date:
    if value is None:
        return dt.date.today()
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    text = str(value).strip()
    if "-" in text:
        return dt.datetime.strptime(text[:10], "%Y-%m-%d").date()
    return dt.datetime.strptime(text, "%Y%m%d").date()


def ingest_date(db: Session, trade_date: Optional[DateLike] = None) -> IngestJob:
    day = _as_date(trade_date)
    job = IngestJob(trade_date=day, status="running")
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        rows = fetch_institutional(day)
        twse_n = 0
        tpex_n = 0
        for row in rows:
            existing = db.scalar(
                select(InstitutionalDaily).where(
                    InstitutionalDaily.trade_date == day,
                    InstitutionalDaily.market == row.market,
                    InstitutionalDaily.code == row.code,
                )
            )
            payload = dict(
                trade_date=day,
                market=row.market,
                code=row.code,
                name=row.name,
                foreign_buy=row.foreign_buy,
                foreign_sell=row.foreign_sell,
                foreign_net=row.foreign_net,
                foreign_dealer_buy=row.foreign_dealer_buy,
                foreign_dealer_sell=row.foreign_dealer_sell,
                foreign_dealer_net=row.foreign_dealer_net,
                trust_buy=row.trust_buy,
                trust_sell=row.trust_sell,
                trust_net=row.trust_net,
                dealer_self_buy=row.dealer_self_buy,
                dealer_self_sell=row.dealer_self_sell,
                dealer_self_net=row.dealer_self_net,
                dealer_hedge_buy=row.dealer_hedge_buy,
                dealer_hedge_sell=row.dealer_hedge_sell,
                dealer_hedge_net=row.dealer_hedge_net,
                dealer_net=row.dealer_net,
                total_net=row.total_net,
                broker_detail=None,
                ingested_at=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None),
            )
            if existing:
                for key, value in payload.items():
                    setattr(existing, key, value)
            else:
                db.add(InstitutionalDaily(**payload))

            if row.market == "twse":
                twse_n += 1
            else:
                tpex_n += 1

        if twse_n == 0 and tpex_n == 0:
            job.status = "empty"
            job.message = "No institutional rows (non-trading day or feed unavailable)"
        else:
            job.status = "success"
            job.message = f"ingested twse={twse_n} tpex={tpex_n}"
        job.twse_rows = twse_n
        job.tpex_rows = tpex_n
        job.finished_at = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
        db.commit()
        db.refresh(job)
        return job
    except Exception as exc:  # noqa: BLE001 - persist failure on job
        job.status = "failed"
        job.message = str(exc)
        job.finished_at = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
        db.commit()
        db.refresh(job)
        raise
