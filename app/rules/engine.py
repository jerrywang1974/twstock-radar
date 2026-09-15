"""Scan engine: run only enabled rule templates with per-rule lookback."""

from __future__ import annotations

import datetime as dt
import json
import math
from dataclasses import dataclass
from typing import Iterable, List

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import InstitutionalDaily, RuleHit
from app.services.filters import apply_exclude_codes, filter_equities, parse_extra_excludes
from app.services.rule_config import get_enabled_rule_map
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


def _recent_rows(
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
        .limit(max(days, 1))
    )
    return list(db.scalars(stmt))


def _streak(rows_newest_first: Iterable[InstitutionalDaily], positive_fn) -> int:
    streak = 0
    for row in rows_newest_first:
        if positive_fn(row):
            streak += 1
        else:
            break
    return streak


def _foreign_net(row: InstitutionalDaily) -> int:
    return row.foreign_net + row.foreign_dealer_net


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


def _top_codes(rows: List[InstitutionalDaily], key_fn, limit: int, min_lots: float) -> set[str]:
    ranked = sorted(rows, key=key_fn, reverse=True)
    out = set()
    for row in ranked:
        if to_lots(key_fn(row)) < min_lots:
            continue
        out.add(row.code)
        if len(out) >= limit:
            break
    return out


def scan_trust_rules(
    db: Session, trade_date: dt.date, settings: Settings | None = None
) -> List[Hit]:
    """Backward-compatible name: scan all enabled templates for trade_date."""
    settings = settings or get_settings()
    day_rows = _prepare_day_rows(db, trade_date, settings)
    if not day_rows:
        return []

    enabled = get_enabled_rule_map(db)
    hits: List[Hit] = []
    min_lots = settings.trust_min_net_lots
    top_k = settings.trust_top_k

    if "trust_top_buy" in enabled:
        buyers = sorted(day_rows, key=lambda r: r.trust_net, reverse=True)
        top = [r for r in buyers if to_lots(r.trust_net) >= min_lots][:top_k]
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
                        "trust_net_lots": to_lots(row.trust_net),
                        "lookback_days": 1,
                    },
                )
            )

    if "foreign_top_buy" in enabled:
        buyers = sorted(day_rows, key=_foreign_net, reverse=True)
        top = [r for r in buyers if to_lots(_foreign_net(r)) >= min_lots][:top_k]
        for row in top:
            hits.append(
                Hit(
                    trade_date=trade_date,
                    code=row.code,
                    name=row.name,
                    rule_id="foreign_top_buy",
                    reason=f"外資買超排行，今日 {to_lots(_foreign_net(row)):.0f} 張",
                    suggested_action="watch",
                    metrics={
                        "foreign_net_lots": to_lots(_foreign_net(row)),
                        "lookback_days": 1,
                    },
                )
            )

    if "foreign_trust_align" in enabled:
        for row in day_rows:
            foreign_net = _foreign_net(row)
            if (
                foreign_net > 0
                and row.trust_net > 0
                and to_lots(row.trust_net) >= min_lots / 2
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
                            "lookback_days": 1,
                        },
                    )
                )

    if "trust_foreign_diverge" in enabled:
        for row in day_rows:
            foreign_net = _foreign_net(row)
            if row.trust_net > 0 and foreign_net < 0 and to_lots(row.trust_net) >= min_lots:
                hits.append(
                    Hit(
                        trade_date=trade_date,
                        code=row.code,
                        name=row.name,
                        rule_id="trust_foreign_diverge",
                        reason="投信買超但外資賣超（意見分歧）",
                        suggested_action="watch",
                        metrics={
                            "trust_net_lots": to_lots(row.trust_net),
                            "foreign_net_lots": to_lots(foreign_net),
                            "lookback_days": 1,
                        },
                    )
                )

    if "dual_top_overlap" in enabled:
        trust_set = _top_codes(day_rows, lambda r: r.trust_net, top_k, min_lots)
        foreign_set = _top_codes(day_rows, _foreign_net, top_k, min_lots)
        overlap = trust_set & foreign_set
        for row in day_rows:
            if row.code not in overlap:
                continue
            hits.append(
                Hit(
                    trade_date=trade_date,
                    code=row.code,
                    name=row.name,
                    rule_id="dual_top_overlap",
                    reason="同日進入外資與投信買超排行",
                    suggested_action="watch",
                    metrics={
                        "trust_net_lots": to_lots(row.trust_net),
                        "foreign_net_lots": to_lots(_foreign_net(row)),
                        "lookback_days": 1,
                    },
                )
            )

    # History-based rules
    for row in day_rows:
        if "trust_streak" in enabled:
            lookback = int(enabled["trust_streak"]["lookback_days"])
            history = _recent_rows(db, row.code, row.market, trade_date, lookback)
            streak = _streak(history, lambda r: r.trust_net > 0)
            if streak >= lookback:
                hits.append(
                    Hit(
                        trade_date=trade_date,
                        code=row.code,
                        name=row.name,
                        rule_id="trust_streak",
                        reason=f"投信連買 {streak} 日（門檻 {lookback}）",
                        suggested_action="buy_bias",
                        metrics={
                            "streak": streak,
                            "lookback_days": lookback,
                            "trust_net_lots": to_lots(row.trust_net),
                        },
                    )
                )

        if "foreign_streak" in enabled:
            lookback = int(enabled["foreign_streak"]["lookback_days"])
            history = _recent_rows(db, row.code, row.market, trade_date, lookback)
            streak = _streak(history, lambda r: _foreign_net(r) > 0)
            if streak >= lookback:
                hits.append(
                    Hit(
                        trade_date=trade_date,
                        code=row.code,
                        name=row.name,
                        rule_id="foreign_streak",
                        reason=f"外資連買 {streak} 日（門檻 {lookback}）",
                        suggested_action="buy_bias",
                        metrics={
                            "streak": streak,
                            "lookback_days": lookback,
                            "foreign_net_lots": to_lots(_foreign_net(row)),
                        },
                    )
                )

        if "total_streak" in enabled:
            lookback = int(enabled["total_streak"]["lookback_days"])
            history = _recent_rows(db, row.code, row.market, trade_date, lookback)
            streak = _streak(history, lambda r: r.total_net > 0)
            if streak >= lookback:
                hits.append(
                    Hit(
                        trade_date=trade_date,
                        code=row.code,
                        name=row.name,
                        rule_id="total_streak",
                        reason=f"三大法人連買 {streak} 日（門檻 {lookback}）",
                        suggested_action="watch",
                        metrics={"streak": streak, "lookback_days": lookback},
                    )
                )

        if "institutional_turn" in enabled:
            lookback = int(enabled["institutional_turn"]["lookback_days"])
            history = _recent_rows(db, row.code, row.market, trade_date, lookback)
            if len(history) >= lookback and row.total_net > 0 and row.trust_net > 0:
                # Older half of the window (excluding today) should be net selling.
                older = history[1:]
                if older:
                    older_sum = sum(r.total_net for r in older)
                    if older_sum < 0:
                        hits.append(
                            Hit(
                                trade_date=trade_date,
                                code=row.code,
                                name=row.name,
                                rule_id="institutional_turn",
                                reason=f"近 {lookback} 日法人由賣轉買",
                                suggested_action="watch",
                                metrics={
                                    "lookback_days": lookback,
                                    "older_total_net_lots": to_lots(older_sum),
                                    "today_total_net_lots": to_lots(row.total_net),
                                },
                            )
                        )

        if "trust_cum_buy" in enabled:
            lookback = int(enabled["trust_cum_buy"]["lookback_days"])
            history = _recent_rows(db, row.code, row.market, trade_date, lookback)
            if len(history) >= lookback:
                cum = sum(r.trust_net for r in history)
                threshold = min_lots * max(lookback / 3.0, 1.0) * 1000
                if cum >= threshold:
                    hits.append(
                        Hit(
                            trade_date=trade_date,
                            code=row.code,
                            name=row.name,
                            rule_id="trust_cum_buy",
                            reason=f"近 {lookback} 日投信累計買超 {to_lots(cum):.0f} 張",
                            suggested_action="watch",
                            metrics={
                                "lookback_days": lookback,
                                "cum_trust_lots": to_lots(cum),
                            },
                        )
                    )

        if "foreign_cum_buy" in enabled:
            lookback = int(enabled["foreign_cum_buy"]["lookback_days"])
            history = _recent_rows(db, row.code, row.market, trade_date, lookback)
            if len(history) >= lookback:
                cum = sum(_foreign_net(r) for r in history)
                threshold = min_lots * max(lookback / 3.0, 1.0) * 1000
                if cum >= threshold:
                    hits.append(
                        Hit(
                            trade_date=trade_date,
                            code=row.code,
                            name=row.name,
                            rule_id="foreign_cum_buy",
                            reason=f"近 {lookback} 日外資累計買超 {to_lots(cum):.0f} 張",
                            suggested_action="watch",
                            metrics={
                                "lookback_days": lookback,
                                "cum_foreign_lots": to_lots(cum),
                            },
                        )
                    )

    if "crowded_trust_fade" in enabled:
        lookback = int(enabled["crowded_trust_fade"]["lookback_days"])
        # Build per-day top sets for recent dates present in DB.
        dates = list(
            db.scalars(
                select(InstitutionalDaily.trade_date)
                .where(InstitutionalDaily.trade_date <= trade_date)
                .distinct()
                .order_by(InstitutionalDaily.trade_date.desc())
                .limit(lookback)
            )
        )
        appear: dict[str, int] = {}
        names: dict[str, str] = {}
        for day in dates:
            rows = _prepare_day_rows(db, day, settings)
            top = _top_codes(rows, lambda r: r.trust_net, top_k, min_lots)
            for row in rows:
                names[row.code] = row.name
            for code in top:
                appear[code] = appear.get(code, 0) + 1
        need = max(1, math.ceil(lookback * 0.6))
        for code, count in appear.items():
            if count >= need:
                hits.append(
                    Hit(
                        trade_date=trade_date,
                        code=code,
                        name=names.get(code, code),
                        rule_id="crowded_trust_fade",
                        reason=f"近 {lookback} 日有 {count} 日進投信買超排行（過熱警示）",
                        suggested_action="sell_bias",
                        metrics={
                            "lookback_days": lookback,
                            "top_appearances": count,
                            "need": need,
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
        f"命中 {len(hits)} 筆（已啟用範本規則；已套用排除與冷卻）",
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
