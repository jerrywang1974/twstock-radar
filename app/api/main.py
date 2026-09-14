from __future__ import annotations

import datetime as dt
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db, init_db
from app.models import Alert, IngestJob, InstitutionalDaily, RuleHit
from app.notify.dispatcher import send_digest
from app.services.pipeline import run_daily_pipeline


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def _startup() -> None:
        init_db()

    def require_token(authorization: Optional[str] = Header(default=None)) -> None:
        if not settings.api_token:
            return
        if not authorization or authorization.removeprefix("Bearer ").strip() != settings.api_token:
            raise HTTPException(status_code=401, detail="Unauthorized")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "app": settings.app_name}

    @app.get("/dashboard")
    def dashboard(db: Session = Depends(get_db), _: None = Depends(require_token)) -> dict:
        job = db.scalar(select(IngestJob).order_by(desc(IngestJob.id)).limit(1))
        day = job.trade_date if job else dt.date.today()
        hit_count = db.scalar(
            select(func.count()).select_from(RuleHit).where(RuleHit.trade_date == day)
        ) or 0
        alert_count = db.scalar(
            select(func.count()).select_from(Alert).where(Alert.trade_date == day)
        ) or 0
        trust_sum = db.scalar(
            select(func.coalesce(func.sum(InstitutionalDaily.trust_net), 0)).where(
                InstitutionalDaily.trade_date == day
            )
        ) or 0
        total_sum = db.scalar(
            select(func.coalesce(func.sum(InstitutionalDaily.total_net), 0)).where(
                InstitutionalDaily.trade_date == day
            )
        ) or 0
        return {
            "trade_date": day.isoformat(),
            "job": None
            if not job
            else {
                "id": job.id,
                "status": job.status,
                "twse_rows": job.twse_rows,
                "tpex_rows": job.tpex_rows,
                "message": job.message,
            },
            "hit_count": hit_count,
            "alert_count": alert_count,
            "trust_net_sum": int(trust_sum),
            "total_net_sum": int(total_sum),
        }

    @app.get("/settings")
    def get_app_settings(_: None = Depends(require_token)) -> dict:
        return {
            "timezone": settings.timezone,
            "ingest_retry_times": settings.ingest_retry_times,
            "rules": {
                "trust_top_k": settings.trust_top_k,
                "trust_streak_days": settings.trust_streak_days,
                "trust_min_net_lots": settings.trust_min_net_lots,
                "alert_cooldown_days": settings.alert_cooldown_days,
            },
            "channels": {
                "telegram": bool(settings.telegram_bot_token and settings.telegram_chat_id),
                "email": bool(settings.smtp_host and settings.smtp_to and settings.smtp_from),
                "slack": bool(settings.slack_webhook_url),
            },
            "rules_catalog": [
                {
                    "id": "trust_top_buy",
                    "name": "投信買超排行",
                    "description": f"今日投信買超 ≥ {settings.trust_min_net_lots} 張，取 Top {settings.trust_top_k}",
                },
                {
                    "id": "trust_streak",
                    "name": "投信連買",
                    "description": f"投信連續買超 ≥ {settings.trust_streak_days} 日",
                },
                {
                    "id": "foreign_trust_align",
                    "name": "外資投信同向",
                    "description": "外資與投信同日買超",
                },
            ],
        }

    @app.post("/channels/test")
    def channels_test(
        db: Session = Depends(get_db),
        _: None = Depends(require_token),
    ) -> dict:
        day = dt.date.today()
        subject = "[twstock-radar] 通道測試"
        body = (
            f"測試時間（UTC）: {dt.datetime.now(dt.timezone.utc).isoformat()}\n"
            "若你收到這則訊息，代表通知通道設定成功。\n"
            "內容僅供系統驗證，非投資建議。"
        )
        alerts = send_digest(db, day, subject, body, settings=settings)
        return {
            "alerts": [
                {
                    "id": a.id,
                    "channel": a.channel,
                    "status": a.status,
                    "error": a.error,
                }
                for a in alerts
            ]
        }

    @app.post("/jobs/run")
    def jobs_run(
        trade_date: Optional[str] = Query(default=None),
        notify: bool = Query(default=True),
        db: Session = Depends(get_db),
        _: None = Depends(require_token),
    ) -> dict:
        return run_daily_pipeline(db, trade_date=trade_date, notify=notify)

    @app.get("/jobs/latest")
    def jobs_latest(db: Session = Depends(get_db), _: None = Depends(require_token)) -> dict:
        job = db.scalar(select(IngestJob).order_by(desc(IngestJob.id)).limit(1))
        if not job:
            return {"job": None}
        return {
            "job": {
                "id": job.id,
                "trade_date": job.trade_date.isoformat(),
                "status": job.status,
                "twse_rows": job.twse_rows,
                "tpex_rows": job.tpex_rows,
                "message": job.message,
            }
        }

    @app.get("/scans/today")
    def scans_today(
        trade_date: Optional[str] = Query(default=None),
        limit: int = Query(default=50, ge=1, le=500),
        db: Session = Depends(get_db),
        _: None = Depends(require_token),
    ) -> dict:
        day = (
            dt.datetime.strptime(trade_date, "%Y-%m-%d").date()
            if trade_date
            else dt.date.today()
        )
        hits = list(
            db.scalars(
                select(RuleHit)
                .where(RuleHit.trade_date == day)
                .order_by(desc(RuleHit.id))
                .limit(limit)
            )
        )
        return {
            "trade_date": day.isoformat(),
            "hits": [
                {
                    "code": h.code,
                    "name": h.name,
                    "rule_id": h.rule_id,
                    "reason": h.reason,
                    "suggested_action": h.suggested_action,
                    "metrics_json": h.metrics_json,
                }
                for h in hits
            ],
        }

    @app.get("/institutional/top")
    def institutional_top(
        trade_date: Optional[str] = Query(default=None),
        field: str = Query(default="trust_net"),
        limit: int = Query(default=20, ge=1, le=200),
        db: Session = Depends(get_db),
        _: None = Depends(require_token),
    ) -> dict:
        day = (
            dt.datetime.strptime(trade_date, "%Y-%m-%d").date()
            if trade_date
            else dt.date.today()
        )
        allowed = {
            "trust_net",
            "foreign_net",
            "dealer_net",
            "total_net",
        }
        if field not in allowed:
            raise HTTPException(status_code=400, detail=f"field must be one of {sorted(allowed)}")
        column = getattr(InstitutionalDaily, field)
        rows = list(
            db.scalars(
                select(InstitutionalDaily)
                .where(InstitutionalDaily.trade_date == day)
                .order_by(desc(column))
                .limit(limit)
            )
        )
        return {
            "trade_date": day.isoformat(),
            "field": field,
            "rows": [
                {
                    "code": r.code,
                    "name": r.name,
                    "market": r.market,
                    "trust_net": r.trust_net,
                    "foreign_net": r.foreign_net,
                    "dealer_net": r.dealer_net,
                    "total_net": r.total_net,
                }
                for r in rows
            ],
        }

    @app.get("/alerts")
    def alerts(
        limit: int = Query(default=20, ge=1, le=200),
        db: Session = Depends(get_db),
        _: None = Depends(require_token),
    ) -> dict:
        rows = list(db.scalars(select(Alert).order_by(desc(Alert.id)).limit(limit)))
        return {
            "alerts": [
                {
                    "id": a.id,
                    "trade_date": a.trade_date.isoformat(),
                    "channel": a.channel,
                    "subject": a.subject,
                    "status": a.status,
                    "error": a.error,
                }
                for a in rows
            ]
        }

    return app


app = create_app()
