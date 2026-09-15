from __future__ import annotations

import datetime as dt

from sqlalchemy import Date, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class InstitutionalDaily(Base):
    __tablename__ = "institutional_daily"
    __table_args__ = (
        UniqueConstraint("trade_date", "market", "code", name="uq_inst_day_market_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[dt.date] = mapped_column(Date, index=True)
    market: Mapped[str] = mapped_column(String(8), index=True)
    code: Mapped[str] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(64), default="")

    foreign_buy: Mapped[int] = mapped_column(Integer, default=0)
    foreign_sell: Mapped[int] = mapped_column(Integer, default=0)
    foreign_net: Mapped[int] = mapped_column(Integer, default=0)
    foreign_dealer_buy: Mapped[int] = mapped_column(Integer, default=0)
    foreign_dealer_sell: Mapped[int] = mapped_column(Integer, default=0)
    foreign_dealer_net: Mapped[int] = mapped_column(Integer, default=0)
    trust_buy: Mapped[int] = mapped_column(Integer, default=0)
    trust_sell: Mapped[int] = mapped_column(Integer, default=0)
    trust_net: Mapped[int] = mapped_column(Integer, default=0)
    dealer_self_buy: Mapped[int] = mapped_column(Integer, default=0)
    dealer_self_sell: Mapped[int] = mapped_column(Integer, default=0)
    dealer_self_net: Mapped[int] = mapped_column(Integer, default=0)
    dealer_hedge_buy: Mapped[int] = mapped_column(Integer, default=0)
    dealer_hedge_sell: Mapped[int] = mapped_column(Integer, default=0)
    dealer_hedge_net: Mapped[int] = mapped_column(Integer, default=0)
    dealer_net: Mapped[int] = mapped_column(Integer, default=0)
    total_net: Mapped[int] = mapped_column(Integer, default=0)

    # Reserved for Phase 5 broker/branch detail (JSON text).
    broker_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingested_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=lambda: dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    )


class IngestJob(Base):
    __tablename__ = "ingest_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[dt.date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    twse_rows: Mapped[int] = mapped_column(Integer, default=0)
    tpex_rows: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=lambda: dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    )
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class RuleHit(Base):
    __tablename__ = "rule_hits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[dt.date] = mapped_column(Date, index=True)
    code: Mapped[str] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    rule_id: Mapped[str] = mapped_column(String(64), index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    suggested_action: Mapped[str] = mapped_column(String(32), default="watch")
    metrics_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=lambda: dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    )


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[dt.date] = mapped_column(Date, index=True)
    channel: Mapped[str] = mapped_column(String(32))
    subject: Mapped[str] = mapped_column(String(256), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=lambda: dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    )


class AiInsight(Base):
    __tablename__ = "ai_insights"
    __table_args__ = (
        UniqueConstraint("trade_date", "code", "rule_id", name="uq_ai_day_code_rule"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[dt.date] = mapped_column(Date, index=True)
    code: Mapped[str] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    rule_id: Mapped[str] = mapped_column(String(64), default="")
    rationale: Mapped[str] = mapped_column(Text, default="")
    action_bias: Mapped[str] = mapped_column(String(32), default="watch")
    action_command: Mapped[str] = mapped_column(String(32), default="HOLD")
    action_plan: Mapped[str] = mapped_column(Text, default="")
    risk_level: Mapped[str] = mapped_column(String(16), default="medium")
    growth_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    upside_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    downside_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    avoid_reason: Mapped[str] = mapped_column(Text, default="")
    growth_thesis: Mapped[str] = mapped_column(Text, default="")
    buy_ref: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_ref: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_ref: Mapped[float | None] = mapped_column(Float, nullable=True)
    watch_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    watch_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_close: Mapped[float | None] = mapped_column(Float, nullable=True)
    model: Mapped[str] = mapped_column(String(64), default="")
    raw_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=lambda: dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    )
