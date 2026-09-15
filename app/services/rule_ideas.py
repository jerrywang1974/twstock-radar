"""AI-generated screening-rule ideas for operator reference.

These ideas are NOT executed by the scanner. They are suggestions you can
later implement or tune as real rules.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
from typing import List

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import InstitutionalDaily, RuleHit, RuleIdea
from twstock.institutional import to_lots

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是台股籌碼選股規則設計師。"
    "根據「已啟用規則」與「當日市場摘要」，提出可實作的新規則構想，供使用者參考。"
    "規則必須可量化、可用現有三大法人／投信／股價欄位近似實作；不要要求無法取得的內線資料。"
    "回覆必須是 JSON 陣列，不要 markdown。"
)

ACTIVE_RULES = [
    {
        "id": "trust_top_buy",
        "name": "投信買超排行",
        "logic": "當日投信買超張數達門檻後取 Top K",
    },
    {
        "id": "trust_streak",
        "name": "投信連買",
        "logic": "投信連續 N 日淨買超",
    },
    {
        "id": "foreign_trust_align",
        "name": "外資投信同向",
        "logic": "外資與投信同日淨買超",
    },
]


def _extract_json_list(text: str) -> list:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "ideas" in data:
            data = data["ideas"]
        if not isinstance(data, list):
            raise ValueError("expected JSON list")
        return data
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", text, flags=re.DOTALL)
        if not match:
            raise
        data = json.loads(match.group(0))
        if not isinstance(data, list):
            raise ValueError("expected JSON list")
        return data


def _call_xai(prompt: str, settings: Settings) -> str:
    if not settings.xai_api_key:
        raise RuntimeError("XAI_API_KEY is not configured")
    from openai import OpenAI

    client = OpenAI(api_key=settings.xai_api_key, base_url=settings.ai_base_url)
    try:
        response = client.responses.create(
            model=settings.ai_model,
            instructions=SYSTEM_PROMPT,
            input=prompt,
        )
        text = getattr(response, "output_text", None)
        if text and text.strip():
            return text
        raise RuntimeError(f"Empty responses output: {response!r}")
    except Exception as exc:
        logger.warning("responses API failed, falling back to chat.completions: %s", exc)

    completion = client.chat.completions.create(
        model=settings.ai_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
    )
    return completion.choices[0].message.content or "[]"


def build_market_snapshot(db: Session, trade_date: dt.date, settings: Settings) -> dict:
    rows = list(
        db.scalars(
            select(InstitutionalDaily).where(InstitutionalDaily.trade_date == trade_date)
        )
    )
    if not rows:
        return {"trade_date": trade_date.isoformat(), "row_count": 0}

    trust_sorted = sorted(rows, key=lambda r: r.trust_net, reverse=True)
    foreign_sorted = sorted(
        rows, key=lambda r: r.foreign_net + r.foreign_dealer_net, reverse=True
    )
    total_sorted = sorted(rows, key=lambda r: r.total_net, reverse=True)

    def pack(items, net_fn):
        out = []
        for r in items[:8]:
            out.append(
                {
                    "code": r.code,
                    "name": r.name,
                    "trust_lots": round(to_lots(r.trust_net), 1),
                    "foreign_lots": round(to_lots(r.foreign_net + r.foreign_dealer_net), 1),
                    "total_lots": round(to_lots(r.total_net), 1),
                    "net_focus_lots": round(to_lots(net_fn(r)), 1),
                }
            )
        return out

    hit_count = db.scalar(
        select(func.count()).select_from(RuleHit).where(RuleHit.trade_date == trade_date)
    ) or 0
    hit_rules = list(
        db.execute(
            select(RuleHit.rule_id, func.count())
            .where(RuleHit.trade_date == trade_date)
            .group_by(RuleHit.rule_id)
        )
    )

    return {
        "trade_date": trade_date.isoformat(),
        "row_count": len(rows),
        "thresholds": {
            "trust_top_k": settings.trust_top_k,
            "trust_streak_days": settings.trust_streak_days,
            "trust_min_net_lots": settings.trust_min_net_lots,
        },
        "active_rules": ACTIVE_RULES,
        "hit_count": hit_count,
        "hits_by_rule": {rid: int(cnt) for rid, cnt in hit_rules},
        "top_trust": pack(trust_sorted, lambda r: r.trust_net),
        "top_foreign": pack(foreign_sorted, lambda r: r.foreign_net + r.foreign_dealer_net),
        "top_total": pack(total_sorted, lambda r: r.total_net),
    }


def _fallback_ideas(trade_date: dt.date) -> list[dict]:
    """Static reference ideas when AI is off or fails."""
    return [
        {
            "idea_id": "trust_buy_price_up",
            "title": "投信買超且收紅／站上五日線",
            "logic": "trust_net > 門檻 且 close > open（或 close > ma5）",
            "why": "籌碼偏多同時價格同向，減少「買超但股價弱」的雜訊",
            "data_needed": "投信買賣超 + 日線 OHLCV",
            "risk_notes": "單日收紅可能是反彈，需搭配連買或量能",
            "priority": "high",
            "example_codes": "",
        },
        {
            "idea_id": "foreign_out_trust_in",
            "title": "外資賣超但投信買超（投信獨買）",
            "logic": "foreign_net < 0 且 trust_net > 門檻",
            "why": "找出本土投信與外資意見分歧的標的，作對照觀察",
            "data_needed": "外資／投信買賣超",
            "risk_notes": "外資賣壓大時短線波動可能仍大",
            "priority": "medium",
            "example_codes": "",
        },
        {
            "idea_id": "three_day_total_turn",
            "title": "三大法人由賣轉買（翻多）",
            "logic": "前 1–2 日 total_net < 0，今日 total_net > 0 且 trust_net > 0",
            "why": "捕捉法人態度轉折，而不是只看單日排行",
            "data_needed": "近三日三大法人合計",
            "risk_notes": "假突破常見，可要求連續兩日轉正",
            "priority": "high",
            "example_codes": "",
        },
        {
            "idea_id": "trust_streak_low_range",
            "title": "投信連買且位處區間下半",
            "logic": "trust_streak ≥ N 且 range_position ≤ 0.5",
            "why": "連買發生在相對低位，追高風險較低",
            "data_needed": "投信連買 + 近十日高低",
            "risk_notes": "低位可能是下跌趨勢中繼",
            "priority": "high",
            "example_codes": "",
        },
        {
            "idea_id": "dealer_hedge_spike",
            "title": "自營避險異常放大（觀察用）",
            "logic": "|dealer_hedge_net| 相對近五日均值放大且 total_net 同向",
            "why": "避險單常與權證／選擇權有關，可當波動警訊",
            "data_needed": "自營避險買賣超時間序列",
            "risk_notes": "解讀難度高，建議只作警示不直接當買訊",
            "priority": "low",
            "example_codes": "",
        },
        {
            "idea_id": "crowded_top_fade",
            "title": "投信買超排行過熱（反向觀察）",
            "logic": "連續多日都在投信買超 Top K，且 range_position ≥ 0.9",
            "why": "過熱排行常伴隨追價，可作減碼／迴避參考",
            "data_needed": "多日 Top K 名單 + 區間位置",
            "risk_notes": "強勢股也可能續強，反向規則需嚴格風控",
            "priority": "medium",
            "example_codes": "",
        },
    ]


def _build_prompt(snapshot: dict) -> str:
    return f"""
請根據下列市場摘要，提出 6~8 條「可實作的新掃市規則構想」，供使用者當參考筆記。
不要重複已經啟用的規則（trust_top_buy / trust_streak / foreign_trust_align），但可以提出其進階變體。

市場摘要 JSON:
{json.dumps(snapshot, ensure_ascii=False)}

每條規則請給:
- idea_id: 英文蛇形短碼
- title: 繁中標題
- logic: 可量化條件（可用 trust_net/foreign_net/total_net/連買天數/range_position/ma5 等）
- why: 為什麼值得觀察
- data_needed: 需要哪些資料
- risk_notes: 風險或誤判點
- priority: high|medium|low
- example_codes: 若摘要中有合適例子就填代碼（逗號分隔），否則空字串

只輸出 JSON 陣列。
""".strip()


def ideas_as_dict(rows: List[RuleIdea]) -> list[dict]:
    return [
        {
            "id": r.id,
            "trade_date": r.trade_date.isoformat(),
            "idea_id": r.idea_id,
            "title": r.title,
            "logic": r.logic,
            "why": r.why,
            "data_needed": r.data_needed,
            "risk_notes": r.risk_notes,
            "priority": r.priority,
            "example_codes": r.example_codes,
            "model": r.model,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def generate_rule_ideas(
    db: Session,
    trade_date: dt.date,
    settings: Settings | None = None,
    *,
    use_ai: bool = True,
) -> List[RuleIdea]:
    settings = settings or get_settings()
    snapshot = build_market_snapshot(db, trade_date, settings)

    raw_items: list[dict]
    model_name = "fallback"
    raw_json = "{}"

    if use_ai and settings.ai_enabled and settings.xai_api_key and snapshot.get("row_count", 0) > 0:
        try:
            raw_text = _call_xai(_build_prompt(snapshot), settings)
            raw_items = _extract_json_list(raw_text)
            model_name = settings.ai_model
            raw_json = raw_text
        except Exception as exc:  # noqa: BLE001
            logger.exception("AI rule-idea generation failed: %s", exc)
            raw_items = _fallback_ideas(trade_date)
            model_name = f"fallback:{exc}"
            raw_json = json.dumps({"error": str(exc)}, ensure_ascii=False)
    else:
        raw_items = _fallback_ideas(trade_date)
        model_name = "fallback"
        raw_json = json.dumps({"snapshot_rows": snapshot.get("row_count", 0)}, ensure_ascii=False)

    # Replace ideas for this trade_date (keep history by date, refresh same day).
    old = list(db.scalars(select(RuleIdea).where(RuleIdea.trade_date == trade_date)))
    for row in old:
        db.delete(row)
    db.flush()

    saved: List[RuleIdea] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        entity = RuleIdea(
            trade_date=trade_date,
            idea_id=str(item.get("idea_id") or item.get("id") or "")[:64],
            title=str(item.get("title") or "")[:128],
            logic=str(item.get("logic") or ""),
            why=str(item.get("why") or ""),
            data_needed=str(item.get("data_needed") or ""),
            risk_notes=str(item.get("risk_notes") or ""),
            priority=str(item.get("priority") or "medium")[:16],
            example_codes=str(item.get("example_codes") or "")[:256],
            model=model_name,
            raw_json=raw_json if len(raw_items) <= 1 else json.dumps(item, ensure_ascii=False),
            created_at=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None),
        )
        db.add(entity)
        saved.append(entity)

    db.commit()
    for entity in saved:
        db.refresh(entity)
    return saved


def list_rule_ideas(
    db: Session, trade_date: dt.date | None = None, limit: int = 50
) -> List[RuleIdea]:
    stmt = select(RuleIdea).order_by(desc(RuleIdea.id)).limit(limit)
    if trade_date is not None:
        stmt = (
            select(RuleIdea)
            .where(RuleIdea.trade_date == trade_date)
            .order_by(desc(RuleIdea.id))
            .limit(limit)
        )
    return list(db.scalars(stmt))
