from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from typing import Iterable, List

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import InstitutionalDaily, RuleHit
from app.services.filters import apply_exclude_codes, filter_equities, parse_extra_excludes
from twstock.institutional import to_lots


@dataclass
class Hit:
    trade_date: dt.date
    code: str
    name: str
    rule_id: str
    reason: str
    suggested_action: str
    metrics: dict


def _recent_trust_rows(
    db: Session, code: str, market: str, end: dt.date, days: int
) -> List[InstitutionalDaily]:
    stmt: Select = (
        select(InstitutionalDaily)
        .where(
            InstitutionalDaily.code == code,
            InstitutionalDaily.market == market,
            InstitutionalDaily.trade_date <= end,
        )
        .order_by(InstitutionalDaily.trade_date.desc())
        .limit(days)
    )
    return list(db.scalars(stmt))


def _trust_buy_streak(rows_newest_first: Iterable[InstitutionalDaily]) -> int:
    streak = 0
    for row in rows_newest_first:
        if row.trust_net > 0:
            streak += 1
        else:
            break
    return streak


def _prepare_day_rows(
    db: Session, trade_date: dt.date, settings: Settings
) -> List[InstitutionalDaily]:
    day_rows = list(
        db.scalars(
            select(InstitutionalDaily).where(InstitutionalDaily.trade_date == trade_date)
        )
    )
    day_rows = filter_equities(day_rows)
    day_rows = apply_exclude_codes(day_rows, parse_extra_excludes(settings.exclude_codes))
    return day_rows


def scan_trust_rules(
    db: Session, trade_date: dt.date, settings: Settings | None = None
) -> List[Hit]:
    settings = settings or get_settings()
    day_rows = _prepare_day_rows(db, trade_date, settings)
    if not day_rows:
        return []

    hits: List[Hit] = []

    buyers = sorted(day_rows, key=lambda r: r.trust_net, reverse=True)
    top = [
        r for r in buyers if to_lots(r.trust_net) >= settings.trust_min_net_lots
    ][: settings.trust_top_k]
    for row in top:
        hits.append(
            Hit(
                trade_date=trade_date,
                code=row.code,
                name=row.name,
                rule_id="trust_top_buy",
                reason=f"投信買超排行，今日 {to_lots(row.trust_net):.0f} 張",
                suggested_action="watch",
                metrics={
                    "trust_net_shares": row.trust_net,
                    "trust_net_lots": to_lots(row.trust_net),
                    "total_net_shares": row.total_net,
                },
            )
        )

    for row in day_rows:
        if row.trust_net <= 0:
            continue
        history = _recent_trust_rows(
            db, row.code, row.market, trade_date, settings.trust_streak_days
        )
        streak = _trust_buy_streak(history)
        if streak >= settings.trust_streak_days:
            hits.append(
                Hit(
                    trade_date=trade_date,
                    code=row.code,
                    name=row.name,
                    rule_id="trust_streak",
                    reason=f"投信連買 {streak} 日",
                    suggested_action="buy_bias",
                    metrics={
                        "streak": streak,
                        "trust_net_lots": to_lots(row.trust_net),
                        "foreign_net_lots": to_lots(
                            row.foreign_net + row.foreign_dealer_net
                        ),
                    },
                )
            )

    for row in day_rows:
        foreign_net = row.foreign_net + row.foreign_dealer_net
        if (
            foreign_net > 0
            and row.trust_net > 0
            and to_lots(row.trust_net) >= settings.trust_min_net_lots / 2
        ):
            hits.append(
                Hit(
                    trade_date=trade_date,
                    code=row.code,
                    name=row.name,
                    rule_id="foreign_trust_align",
                    reason="外資與投信同向買超",
                    suggested_action="watch",
                    metrics={
                        "foreign_net_lots": to_lots(foreign_net),
                        "trust_net_lots": to_lots(row.trust_net),
                    },
                )
            )

    return apply_alert_cooldown(db, hits, settings=settings)


def apply_alert_cooldown(
    db: Session,
    hits: List[Hit],
    settings: Settings | None = None,
) -> List[Hit]:
    """Drop hits that already fired for the same code+rule within cooldown days."""
    settings = settings or get_settings()
    cooldown = max(int(settings.alert_cooldown_days), 0)
    if cooldown <= 0 or not hits:
        return hits

    kept: List[Hit] = []
    for hit in hits:
        earliest = hit.trade_date - dt.timedelta(days=cooldown)
        prior = db.scalar(
            select(RuleHit.id)
            .where(
                RuleHit.code == hit.code,
                RuleHit.rule_id == hit.rule_id,
                RuleHit.trade_date >= earliest,
                RuleHit.trade_date < hit.trade_date,
            )
            .limit(1)
        )
        if prior is None:
            kept.append(hit)
    return kept


def persist_hits(db: Session, hits: List[Hit]) -> List[RuleHit]:
    saved: List[RuleHit] = []
    for hit in hits:
        entity = RuleHit(
            trade_date=hit.trade_date,
            code=hit.code,
            name=hit.name,
            rule_id=hit.rule_id,
            reason=hit.reason,
            suggested_action=hit.suggested_action,
            metrics_json=json.dumps(hit.metrics, ensure_ascii=False),
        )
        db.add(entity)
        saved.append(entity)
    db.commit()
    for entity in saved:
        db.refresh(entity)
    return saved


def format_digest(hits: List[Hit], trade_date: dt.date) -> tuple[str, str]:
    subject = f"[twstock-radar] {trade_date.isoformat()} 法人掃市 {len(hits)} 筆命中"
    if not hits:
        body = (
            f"交易日 {trade_date.isoformat()}\n"
            "今日無規則命中。\n"
            "（本訊息為規則觀察結果，非投資建議。）"
        )
        return subject, body

    lines = [
        f"交易日 {trade_date.isoformat()}",
        f"命中 {len(hits)} 筆（投信合計／三大法人規則；已套用排除與冷卻）",
        "",
    ]
    for hit in hits[:40]:
        lines.append(
            f"- {hit.code} {hit.name} | {hit.rule_id} | {hit.reason} | {hit.suggested_action}"
        )
    if len(hits) > 40:
        lines.append(f"... 另有 {len(hits) - 40} 筆省略")
    lines.extend(["", "免責：規則命中僅供觀察，不構成投資建議。"])
    return subject, "\n".join(lines)
