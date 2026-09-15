from __future__ import annotations

import datetime as dt
import json
import logging
import re
from typing import List

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import AiInsight, RuleHit
from app.rules.engine import Hit
from app.services.price_bands import PriceBand, compute_price_band

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是台股籌碼觀察助手。只根據提供的數字撰寫繁中說明。"
    "不可捏造未提供的財報、消息或價格。"
    "回覆必須是單一 JSON 物件，不要 markdown。"
)


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _call_xai(prompt: str, settings: Settings) -> str:
    if not settings.xai_api_key:
        raise RuntimeError("XAI_API_KEY is not configured")

    from openai import OpenAI

    client = OpenAI(api_key=settings.xai_api_key, base_url=settings.ai_base_url)

    # Prefer Responses API.
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
        temperature=0.2,
    )
    content = completion.choices[0].message.content or "{}"
    return content


def _build_prompt(hit: Hit, band: PriceBand) -> str:
    metrics = hit.metrics or {}
    return f"""
請根據以下「已發生的規則命中」撰寫觀察說明（非投資建議）。

股票: {hit.code} {hit.name}
交易日: {hit.trade_date.isoformat()}
規則: {hit.rule_id}
規則原因: {hit.reason}
規則標籤: {hit.suggested_action}
指標: {json.dumps(metrics, ensure_ascii=False)}
價格帶(由近十日行情計算，非目標價):
  last_close={band.last_close}, ma5={band.ma5},
  watch_low={band.watch_low}, watch_high={band.watch_high}, source={band.source}

請只輸出 JSON，欄位如下:
{{
  "rationale": "2-4 句繁中說明，聚焦籌碼與價量關係",
  "action_bias": "watch|buy_bias|sell_bias",
  "risks": "主要風險一句"
}}
""".strip()


def _priority(hit: Hit) -> int:
    order = {"trust_streak": 0, "trust_top_buy": 1, "foreign_trust_align": 2}
    return order.get(hit.rule_id, 9)


def select_hits_for_ai(hits: List[Hit], limit: int) -> List[Hit]:
    """Prefer one insight per code, ranked by rule priority then metrics."""
    ranked = sorted(
        hits,
        key=lambda h: (
            _priority(h),
            -(h.metrics or {}).get("trust_net_lots", 0)
            if isinstance((h.metrics or {}).get("trust_net_lots", 0), (int, float))
            else 0,
            h.code,
        ),
    )
    chosen: List[Hit] = []
    seen: set[str] = set()
    for hit in ranked:
        if hit.code in seen:
            continue
        seen.add(hit.code)
        chosen.append(hit)
        if len(chosen) >= limit:
            break
    return chosen


def hits_from_rule_rows(rows: List[RuleHit]) -> List[Hit]:
    out: List[Hit] = []
    for row in rows:
        try:
            metrics = json.loads(row.metrics_json or "{}")
        except json.JSONDecodeError:
            metrics = {}
        out.append(
            Hit(
                trade_date=row.trade_date,
                code=row.code,
                name=row.name,
                rule_id=row.rule_id,
                reason=row.reason,
                suggested_action=row.suggested_action,
                metrics=metrics,
            )
        )
    return out


def analyze_hits(
    db: Session,
    hits: List[Hit],
    settings: Settings | None = None,
) -> List[AiInsight]:
    settings = settings or get_settings()
    if not settings.ai_enabled:
        logger.info("AI disabled (AI_ENABLED=false)")
        return []
    if not settings.xai_api_key:
        logger.warning("AI enabled but XAI_API_KEY missing")
        return []

    selected = select_hits_for_ai(hits, max(int(settings.ai_max_hits), 0))
    saved: List[AiInsight] = []

    for hit in selected:
        band = compute_price_band(hit.code)
        try:
            raw_text = _call_xai(_build_prompt(hit, band), settings)
            payload = _extract_json(raw_text)
            rationale = str(payload.get("rationale") or "").strip()
            action_bias = str(payload.get("action_bias") or hit.suggested_action).strip()
            risks = str(payload.get("risks") or "").strip()
            if risks:
                rationale = f"{rationale}\n風險：{risks}".strip()
            status_raw = raw_text
        except Exception as exc:  # noqa: BLE001
            logger.exception("AI analyze failed for %s", hit.code)
            rationale = f"AI 解讀失敗，改以規則摘要：{hit.reason}（{exc}）"
            action_bias = hit.suggested_action
            status_raw = json.dumps({"error": str(exc)}, ensure_ascii=False)

        existing = db.scalar(
            select(AiInsight).where(
                AiInsight.trade_date == hit.trade_date,
                AiInsight.code == hit.code,
                AiInsight.rule_id == hit.rule_id,
            )
        )
        fields = dict(
            trade_date=hit.trade_date,
            code=hit.code,
            name=hit.name,
            rule_id=hit.rule_id,
            rationale=rationale,
            action_bias=action_bias,
            watch_low=band.watch_low,
            watch_high=band.watch_high,
            last_close=band.last_close,
            model=settings.ai_model,
            raw_json=status_raw
            if isinstance(status_raw, str)
            else json.dumps(status_raw, ensure_ascii=False),
            created_at=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None),
        )
        if existing:
            for key, value in fields.items():
                setattr(existing, key, value)
            entity = existing
        else:
            entity = AiInsight(**fields)
            db.add(entity)
        saved.append(entity)

    db.commit()
    for entity in saved:
        db.refresh(entity)
    return saved


def analyze_trade_date(
    db: Session,
    trade_date: dt.date,
    settings: Settings | None = None,
) -> List[AiInsight]:
    """Run AI on persisted rule hits for a trade date (no re-ingest)."""
    rows = list(
        db.scalars(
            select(RuleHit)
            .where(RuleHit.trade_date == trade_date)
            .order_by(desc(RuleHit.id))
        )
    )
    return analyze_hits(db, hits_from_rule_rows(rows), settings=settings)


def format_ai_section(insights: List[AiInsight]) -> str:
    if not insights:
        return ""
    lines = ["", "AI 觀察（非投資建議）:"]
    for item in insights[:10]:
        band = ""
        if item.watch_low is not None and item.watch_high is not None:
            band = f" | 觀察區間 {item.watch_low}-{item.watch_high}"
        close = f" | 收 {item.last_close}" if item.last_close is not None else ""
        lines.append(
            f"- {item.code} {item.name} [{item.action_bias}]{close}{band}\n  {item.rationale}"
        )
    return "\n".join(lines)


def insights_as_dict(insights: List[AiInsight]) -> list[dict]:
    return [
        {
            "code": i.code,
            "name": i.name,
            "rule_id": i.rule_id,
            "rationale": i.rationale,
            "action_bias": i.action_bias,
            "watch_low": i.watch_low,
            "watch_high": i.watch_high,
            "last_close": i.last_close,
            "model": i.model,
        }
        for i in insights
    ]
