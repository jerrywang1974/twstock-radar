"""AI observation layer on top of rule hits.

Flow:
1. Take persisted RuleHit rows (already filtered/cooled by the rule engine).
2. Build a PriceBand with objective buy/sell/stop refs from recent OHLCV.
3. Ask xAI for rationale + action_command + action_plan.
4. Clamp any model-returned prices back into the recent range and apply
   risk overlays (e.g. no BUY when already at range high).

Outputs are observational signals only — not investment advice.
"""

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
    "你必須給出清楚可執行的操作指令（action_command）與簡短行動計畫（action_plan）。"
    "參考買賣價只能使用輸入中提供的 buy_ref / sell_ref / stop_ref（可微調但不超出 watch_low~watch_high）。"
    "只根據提供的數字撰寫繁中說明；不可捏造未提供的財報、消息或價格。"
    "若風險偏高，必須避免 BUY，改為 HOLD / WAIT_PULLBACK / REDUCE / SELL / AVOID。"
    "回覆必須是單一 JSON 物件，不要 markdown。"
)

# Stable command vocabulary shown in UI / digests. Keep in sync with docs/AI_NOTES.md.
VALID_ACTION_COMMANDS = {
    "BUY",
    "WAIT_PULLBACK",
    "HOLD",
    "REDUCE",
    "SELL",
    "AVOID",
    "BREAKOUT_WATCH",
}


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
請根據以下「已發生的規則命中」做積極成長＋風險迴避評估，並給出清楚操作指令（非投資建議）。

股票: {hit.code} {hit.name}
交易日: {hit.trade_date.isoformat()}
規則: {hit.rule_id}
規則原因: {hit.reason}
規則標籤: {hit.suggested_action}
籌碼指標: {json.dumps(metrics, ensure_ascii=False)}
價格／空間／客觀參考價(由近十日行情計算):
{json.dumps(band_data, ensure_ascii=False)}

action_command 只能是其一:
BUY | WAIT_PULLBACK | HOLD | REDUCE | SELL | AVOID | BREAKOUT_WATCH

含義:
- BUY: 可偏多進場（通常要有足夠上檔空間且非追高）
- WAIT_PULLBACK: 看好但等回檔到 buy_ref 再考慮
- HOLD: 已持有或觀望，暫不新做
- REDUCE: 減碼／降低曝險
- SELL: 偏空出場／了結
- AVOID: 避開不碰
- BREAKOUT_WATCH: 等站上 sell_ref／區間高點再評估追擊

評估原則（務必遵守）:
1. 風險優先：range_position 接近 1、或 upside/downside < 1，不要給 BUY。
2. 參考價必須基於輸入的 buy_ref/sell_ref/stop_ref；可微調，但必須落在 watch_low~watch_high。
3. action_plan 用 2-4 條短指令，像交易備忘錄（例：回檔到 X 再買；跌破 Y 停損；反彈到 Z 減碼）。
4. 不可捏造財報或新聞。

請只輸出 JSON:
{{
  "rationale": "3-5 句繁中，含籌碼、價位、成長與風險取捨",
  "action_command": "WAIT_PULLBACK",
  "action_plan": "1) ...\\n2) ...\\n3) ...",
  "action_bias": "watch|buy_bias|sell_bias",
  "risk_level": "low|medium|high|avoid",
  "growth_score": 1,
  "growth_thesis": "一句成長理由（若無則空字串）",
  "avoid_reason": "一句應迴避／減碼理由（若無則空字串）",
  "risks": "主要風險一句",
  "buy_ref": {band.buy_ref},
  "sell_ref": {band.sell_ref},
  "stop_ref": {band.stop_ref}
}}
""".strip()


def _clamp_ref(value: float | None, low: float | None, high: float | None, fallback: float | None):
    """Keep model-adjusted refs inside the objective band when bounds exist."""
    if value is None:
        return fallback
    if low is not None:
        value = max(value, low)
    if high is not None:
        value = min(value, high)
    return round(float(value), 2)


def _normalize_action_command(raw: str, action_bias: str, risk_level: str) -> str:
    """Map free-form model text onto the fixed command set + risk gate."""
    cmd = (raw or "").strip().upper().replace(" ", "_")
    aliases = {
        "BUY_BIAS": "BUY",
        "SELL_BIAS": "SELL",
        "WATCH": "HOLD",
        "ON_HOLD": "HOLD",
        "HOLD_ON": "HOLD",
        "PULLBACK": "WAIT_PULLBACK",
        "WAIT": "WAIT_PULLBACK",
        "ADD": "BUY",
        "TRIM": "REDUCE",
        "CUT": "SELL",
    }
    cmd = aliases.get(cmd, cmd)
    if cmd not in VALID_ACTION_COMMANDS:
        if action_bias == "buy_bias":
            cmd = "WAIT_PULLBACK"
        elif action_bias == "sell_bias":
            cmd = "REDUCE"
        else:
            cmd = "HOLD"
    # Never allow an aggressive BUY when the model itself flagged elevated risk.
    if risk_level in {"high", "avoid"} and cmd == "BUY":
        cmd = "WAIT_PULLBACK" if risk_level == "high" else "AVOID"
    return cmd


def _default_action_plan(cmd: str, buy_ref, sell_ref, stop_ref) -> str:
    return (
        f"1) 操作指令：{cmd}\n"
        f"2) 參考買進／承接：{buy_ref}\n"
        f"3) 參考賣出／減碼：{sell_ref}\n"
        f"4) 防守／停損參考：{stop_ref}"
    )


def _priority(hit: Hit) -> int:
    order = {"trust_streak": 0, "foreign_trust_align": 1, "trust_top_buy": 2}
    return order.get(hit.rule_id, 9)


def select_hits_for_ai(
    hits: List[Hit], limit: int, prefer_upside: bool = True
) -> List[Hit]:
    """Dedupe by code (one AI card per symbol) with a wider pool for upside re-rank."""
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
    """Generate/persist AI insights for the given rule hits."""
    settings = settings or get_settings()
    if not settings.ai_enabled:
        logger.info("AI disabled (AI_ENABLED=false)")
        return []
    if not settings.xai_api_key:
        logger.warning("AI enabled but XAI_API_KEY missing")
        return []

    limit = max(int(settings.ai_max_hits), 0)
    candidates = select_hits_for_ai(hits, limit, prefer_upside=settings.ai_prefer_upside)
    # Price bands are fetched before the LLM call so prompts include objective refs.
    paired: List[tuple[Hit, PriceBand]] = []
    for hit in candidates:
        paired.append((hit, compute_price_band(hit.code)))
    selected = _rank_with_bands(paired, limit, settings.ai_prefer_upside)

    saved: List[AiInsight] = []
    for hit, band in selected:
        buy_ref = band.buy_ref
        sell_ref = band.sell_ref
        stop_ref = band.stop_ref
        action_command = "HOLD"
        action_plan = _default_action_plan("HOLD", buy_ref, sell_ref, stop_ref)
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
            action_command = _normalize_action_command(
                str(payload.get("action_command") or ""), action_bias, risk_level
            )
            action_plan = str(payload.get("action_plan") or "").strip()
            buy_ref = _clamp_ref(
                _safe_float(payload.get("buy_ref")),
                band.watch_low,
                band.watch_high,
                band.buy_ref,
            )
            sell_ref = _clamp_ref(
                _safe_float(payload.get("sell_ref")),
                band.watch_low,
                band.watch_high,
                band.sell_ref,
            )
            stop_ref = _clamp_ref(
                _safe_float(payload.get("stop_ref")),
                None,
                band.watch_high,
                band.stop_ref,
            )
            if stop_ref is not None and band.watch_low is not None:
                # Stop should not sit above the recent low zone aggressively.
                stop_ref = min(stop_ref, band.watch_low)

            # Hard risk overlays from quant bands (aggressive avoidance).
            if band.range_position is not None and band.range_position >= 0.95:
                risk_level = "high" if risk_level == "low" else risk_level
                if action_bias == "buy_bias":
                    action_bias = "watch"
                if action_command == "BUY":
                    action_command = "BREAKOUT_WATCH"
                if not avoid_reason:
                    avoid_reason = "價位已接近近十日區間上緣，追高風險偏高"
            if (
                band.upside_pct is not None
                and band.downside_pct is not None
                and band.downside_pct > 0
                and (band.upside_pct / band.downside_pct) < 0.8
                and action_command == "BUY"
            ):
                action_command = "WAIT_PULLBACK"
                action_bias = "watch"
                risk_level = "high"
                if not avoid_reason:
                    avoid_reason = (
                        f"上檔空間 {band.upside_pct}% 低於下檔風險 {band.downside_pct}%，報酬風險比不佳"
                    )
            if risk_level == "avoid":
                action_command = "AVOID"
                if action_bias == "buy_bias":
                    action_bias = "sell_bias"

            if not action_plan:
                action_plan = _default_action_plan(
                    action_command, buy_ref, sell_ref, stop_ref
                )

            extra_lines = [
                f"操作指令：{action_command}",
                f"參考價：買 {buy_ref}／賣 {sell_ref}／停損 {stop_ref}",
            ]
            if growth_thesis:
                extra_lines.append(f"成長：{growth_thesis}")
            if avoid_reason:
                extra_lines.append(f"迴避：{avoid_reason}")
            if risks:
                extra_lines.append(f"風險：{risks}")
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
            action_command = "HOLD"
            action_plan = _default_action_plan(
                action_command, buy_ref, sell_ref, stop_ref
            )
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
            action_command=action_command,
            action_plan=action_plan,
            risk_level=risk_level,
            growth_score=growth_score,
            upside_pct=band.upside_pct,
            downside_pct=band.downside_pct,
            avoid_reason=avoid_reason,
            growth_thesis=growth_thesis,
            buy_ref=buy_ref,
            sell_ref=sell_ref,
            stop_ref=stop_ref,
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
    lines = ["", "AI 操作計畫（非投資建議）:"]
    for item in insights[:15]:
        close = f"收 {item.last_close}" if item.last_close is not None else ""
        refs = f"買 {item.buy_ref}／賣 {item.sell_ref}／停 {item.stop_ref}"
        lines.append(
            f"- {item.code} {item.name} => 【{item.action_command}】"
            f" | {close} | {refs} | 風險 {item.risk_level}"
        )
        if item.action_plan:
            lines.append(f"  計畫：{item.action_plan.replace(chr(10), ' / ')}")
        lines.append(f"  {item.rationale.splitlines()[0] if item.rationale else ''}")
    return "\n".join(lines)


def insights_as_dict(insights: List[AiInsight]) -> list[dict]:
    return [
        {
            "code": i.code,
            "name": i.name,
            "rule_id": i.rule_id,
            "rationale": i.rationale,
            "action_bias": i.action_bias,
            "action_command": i.action_command,
            "action_plan": i.action_plan,
            "risk_level": i.risk_level,
            "growth_score": i.growth_score,
            "upside_pct": i.upside_pct,
            "downside_pct": i.downside_pct,
            "avoid_reason": i.avoid_reason,
            "growth_thesis": i.growth_thesis,
            "buy_ref": i.buy_ref,
            "sell_ref": i.sell_ref,
            "stop_ref": i.stop_ref,
            "watch_low": i.watch_low,
            "watch_high": i.watch_high,
            "last_close": i.last_close,
            "model": i.model,
        }
        for i in insights
    ]
