from __future__ import annotations

import datetime as dt
import json
import re
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import AiInsight
from app.rules.engine import Hit
from app.services.price_bands import PriceBand, compute_price_band
from twstock.institutional import to_lots


def _extract_json(text: str) -> dict:
    text = text.strip()
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
    # Prefer Responses API; fall back to chat.completions for older SDKs.
    try:
        response = client.responses.create(model=settings.ai_model, input=prompt)
        text = getattr(response, "output_text", None)
        if text:
            return text
    except Exception:
        pass

    completion = client.chat.completions.create(
        model=settings.ai_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是台股籌碼觀察助手。只根據提供的數字撰寫繁中說明。"
                    "不可捏造未提供的財報或消息。回覆必須是 JSON。"
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return completion.choices[0].message.content or "{}"


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


def analyze_hits(
    db: Session,
    hits: List[Hit],
    settings: Settings | None = None,
) -> List[AiInsight]:
    settings = settings or get_settings()
    if not settings.ai_enabled:
        return []
    if not settings.xai_api_key:
        return []

    selected = hits[: max(int(settings.ai_max_hits), 0)]
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
            rationale = (
                f"AI 解讀失敗，改以規則摘要：{hit.reason}（{exc}）"
            )
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
