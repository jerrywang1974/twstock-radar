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
    "你是偏積極、但風險優先的台股籌碼／成長觀察助手。"
    "目標：找出值得追蹤的成長機會，同時明確標出應迴避的風險。"
    "只根據提供的數字撰寫繁中說明；不可捏造未提供的財報、消息或價格。"
    "若風險偏高，必須把 action_bias 設為 sell_bias 或 watch，並填 avoid_reason。"
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
        temperature=0.25,
    )
    return completion.choices[0].message.content or "{}"


def _build_prompt(hit: Hit, band: PriceBand) -> str:
    metrics = hit.metrics or {}
    band_data = band.as_prompt_dict()
    return f"""
請根據以下「已發生的規則命中」做積極成長＋風險迴避評估（非投資建議）。

股票: {hit.code} {hit.name}
交易日: {hit.trade_date.isoformat()}
規則: {hit.rule_id}
規則原因: {hit.reason}
規則標籤: {hit.suggested_action}
籌碼指標: {json.dumps(metrics, ensure_ascii=False)}
價格／空間指標(由近十日行情計算，非目標價):
{json.dumps(band_data, ensure_ascii=False)}

評估原則（務必遵守）:
1. 風險優先：若 downside_pct 明顯大於 upside_pct、或 range_position 接近 1（已近區間高點）、
   或收盤遠高於均線且籌碼僅單日暴衝，傾向降級為 watch / sell_bias，並寫清 avoid_reason。
2. 成長空間：用 upside_pct、ma5_bias_pct、投信／外資同向與連買，評估成長分數 growth_score(1-10)。
3. 報酬風險比：若 upside_pct / max(downside_pct,0.1) < 1，通常不宜 buy_bias。
4. 不可捏造營收、本益比、產業新聞；沒有的資料就不要寫。

請只輸出 JSON:
{{
  "rationale": "3-5 句繁中，含籌碼、價位區間位置、成長與風險取捨",
  "action_bias": "watch|buy_bias|sell_bias",
  "risk_level": "low|medium|high|avoid",
  "growth_score": 1,
  "growth_thesis": "一句成長理由（若無則空字串）",
  "avoid_reason": "一句應迴避／減碼理由（若無則空字串）",
  "risks": "主要風險一句"
}}
""".strip()


def _priority(hit: Hit) -> int:
    order = {"trust_streak": 0, "foreign_trust_align": 1, "trust_top_buy": 2}
    return order.get(hit.rule_id, 9)


def select_hits_for_ai(
    hits: List[Hit], limit: int, prefer_upside: bool = True
) -> List[Hit]:
    """One insight per code; optionally enrich-sort later after bands.

    First pass keeps rule priority; caller may re-rank with bands.
    """
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
    # Take a wider candidate pool if we will re-rank by upside.
    pool_limit = max(limit * 3, limit) if prefer_upside else limit
    for hit in ranked:
        if hit.code in seen:
            continue
        seen.add(hit.code)
        chosen.append(hit)
        if len(chosen) >= pool_limit:
            break
    return chosen


def _rank_with_bands(
    pairs: List[tuple[Hit, PriceBand]], limit: int, prefer_upside: bool
) -> List[tuple[Hit, PriceBand]]:
    def score(item: tuple[Hit, PriceBand]) -> tuple:
        hit, band = item
        upside = band.upside_pct if band.upside_pct is not None else -999
        downside = band.downside_pct if band.downside_pct is not None else 999
        ratio = upside / downside if downside and downside > 0 else upside
        # Prefer not already at range top.
        near_high_penalty = 0
        if band.range_position is not None and band.range_position >= 0.9:
            near_high_penalty = 1
        trust = (hit.metrics or {}).get("trust_net_lots", 0) or 0
        if prefer_upside:
            return (near_high_penalty, -ratio, -upside, -float(trust), _priority(hit))
        return (_priority(hit), -float(trust), -ratio)

    return sorted(pairs, key=score)[:limit]


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


def _safe_float(value, default=None):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


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

    limit = max(int(settings.ai_max_hits), 0)
    candidates = select_hits_for_ai(hits, limit, prefer_upside=settings.ai_prefer_upside)
    paired: List[tuple[Hit, PriceBand]] = []
    for hit in candidates:
        paired.append((hit, compute_price_band(hit.code)))
    selected = _rank_with_bands(paired, limit, settings.ai_prefer_upside)

    saved: List[AiInsight] = []
    for hit, band in selected:
        try:
            raw_text = _call_xai(_build_prompt(hit, band), settings)
            payload = _extract_json(raw_text)
            rationale = str(payload.get("rationale") or "").strip()
            action_bias = str(payload.get("action_bias") or hit.suggested_action).strip()
            risk_level = str(payload.get("risk_level") or "medium").strip().lower()
            growth_score = _safe_float(payload.get("growth_score"))
            growth_thesis = str(payload.get("growth_thesis") or "").strip()
            avoid_reason = str(payload.get("avoid_reason") or "").strip()
            risks = str(payload.get("risks") or "").strip()

            # Hard risk overlays from quant bands (aggressive avoidance).
            if band.range_position is not None and band.range_position >= 0.95:
                risk_level = "high" if risk_level == "low" else risk_level
                if action_bias == "buy_bias":
                    action_bias = "watch"
                if not avoid_reason:
                    avoid_reason = "價位已接近近十日區間上緣，追高風險偏高"
            if (
                band.upside_pct is not None
                and band.downside_pct is not None
                and band.downside_pct > 0
                and (band.upside_pct / band.downside_pct) < 0.8
                and action_bias == "buy_bias"
            ):
                action_bias = "watch"
                risk_level = "high"
                if not avoid_reason:
                    avoid_reason = (
                        f"上檔空間 {band.upside_pct}% 低於下檔風險 {band.downside_pct}%，報酬風險比不佳"
                    )
            if risk_level == "avoid" and action_bias == "buy_bias":
                action_bias = "sell_bias"

            extra_lines = []
            if growth_thesis:
                extra_lines.append(f"成長：{growth_thesis}")
            if avoid_reason:
                extra_lines.append(f"迴避：{avoid_reason}")
            if risks:
                extra_lines.append(f"風險：{risks}")
            if extra_lines:
                rationale = (rationale + "\n" + "\n".join(extra_lines)).strip()

            status_raw = raw_text
        except Exception as exc:  # noqa: BLE001
            logger.exception("AI analyze failed for %s", hit.code)
            rationale = f"AI 解讀失敗，改以規則摘要：{hit.reason}（{exc}）"
            action_bias = hit.suggested_action
            risk_level = "medium"
            growth_score = None
            growth_thesis = ""
            avoid_reason = ""
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
            risk_level=risk_level,
            growth_score=growth_score,
            upside_pct=band.upside_pct,
            downside_pct=band.downside_pct,
            avoid_reason=avoid_reason,
            growth_thesis=growth_thesis,
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
    lines = ["", "AI 觀察（風險優先／成長空間，非投資建議）:"]
    for item in insights[:15]:
        band = ""
        if item.watch_low is not None and item.watch_high is not None:
            band = f" | 觀察區間 {item.watch_low}-{item.watch_high}"
        close = f" | 收 {item.last_close}" if item.last_close is not None else ""
        growth = f" | 成長分 {item.growth_score}" if item.growth_score is not None else ""
        risk = f" | 風險 {item.risk_level}"
        rr = ""
        if item.upside_pct is not None and item.downside_pct is not None:
            rr = f" | 上/下 {item.upside_pct}%/{item.downside_pct}%"
        lines.append(
            f"- {item.code} {item.name} [{item.action_bias}]{close}{band}{growth}{risk}{rr}\n"
            f"  {item.rationale}"
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
            "risk_level": i.risk_level,
            "growth_score": i.growth_score,
            "upside_pct": i.upside_pct,
            "downside_pct": i.downside_pct,
            "avoid_reason": i.avoid_reason,
            "growth_thesis": i.growth_thesis,
            "watch_low": i.watch_low,
            "watch_high": i.watch_high,
            "last_close": i.last_close,
            "model": i.model,
        }
        for i in insights
    ]
