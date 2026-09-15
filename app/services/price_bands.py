"""Objective price context for AI prompts.

Reference prices are derived from recent OHLCV only (not from the LLM).
The model may fine-tune them later, but ai_analysis clamps results back
into [watch_low, watch_high].
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional


@dataclass
class PriceBand:
    last_close: Optional[float]
    ma5: Optional[float]
    ma20: Optional[float]
    watch_low: Optional[float]
    watch_high: Optional[float]
    upside_pct: Optional[float]
    downside_pct: Optional[float]
    ma5_bias_pct: Optional[float]
    range_position: Optional[float]  # 0 = at recent low, 1 = at recent high
    buy_ref: Optional[float]  # pullback / accumulate zone
    sell_ref: Optional[float]  # reduce / take-profit zone near recent high
    stop_ref: Optional[float]  # defensive invalidation under recent low
    source: str

    def as_prompt_dict(self) -> dict:
        return asdict(self)


def _pct(numer: float, denom: float) -> Optional[float]:
    if denom == 0:
        return None
    return round((numer / denom) * 100.0, 2)


def _round_price(value: float) -> float:
    # Taiwan stocks: keep 2 decimals for most names.
    return round(value, 2)


def _objective_refs(
    last_close: float,
    ma5: Optional[float],
    watch_low: float,
    watch_high: float,
) -> tuple[float, float, float]:
    """Compute buy/sell/stop refs from recent range and MA5.

    buy_ref  ~ lower of MA5 and midpoint(low, close) — wait-for-pullback zone
    sell_ref ~ recent high — reduce / resistance reference
    stop_ref ~ slightly below recent low — invalidation / defense
    """
    pullback_anchor = ma5 if ma5 is not None else (watch_low + last_close) / 2.0
    buy_ref = _round_price(min(pullback_anchor, (watch_low + last_close) / 2.0))
    buy_ref = min(max(buy_ref, watch_low), max(last_close, watch_low))
    sell_ref = _round_price(watch_high)
    stop_ref = _round_price(watch_low * 0.985)
    if stop_ref >= buy_ref:
        stop_ref = _round_price(watch_low)
    return buy_ref, sell_ref, stop_ref

def compute_price_band(code: str) -> PriceBand:
    """Derive observation band, ratios, and objective buy/sell/stop refs."""
    empty = PriceBand(
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        "empty",
    )
    try:
        from twstock import Stock

        stock = Stock(code, initial_fetch=True)
        closes = [float(c) for c in stock.close if c is not None]
        lows = [float(v) for v in stock.low if v is not None]
        highs = [float(v) for v in stock.high if v is not None]
        if not closes:
            return empty

        last_close = closes[-1]
        window = min(10, len(closes))
        recent_lows = lows[-window:] or [last_close]
        recent_highs = highs[-window:] or [last_close]
        ma5 = round(sum(closes[-5:]) / 5.0, 2) if len(closes) >= 5 else None
        ma20 = round(sum(closes[-20:]) / 20.0, 2) if len(closes) >= 20 else None
        watch_low = round(min(recent_lows), 2)
        watch_high = round(max(recent_highs), 2)

        upside_pct = _pct(watch_high - last_close, last_close)
        downside_pct = _pct(last_close - watch_low, last_close)
        ma5_bias_pct = _pct(last_close - ma5, ma5) if ma5 is not None else None
        span = watch_high - watch_low
        range_position = (
            round((last_close - watch_low) / span, 3) if span > 0 else None
        )
        buy_ref, sell_ref, stop_ref = _objective_refs(
            last_close, ma5, watch_low, watch_high
        )

        return PriceBand(
            last_close=last_close,
            ma5=ma5,
            ma20=ma20,
            watch_low=watch_low,
            watch_high=watch_high,
            upside_pct=upside_pct,
            downside_pct=downside_pct,
            ma5_bias_pct=ma5_bias_pct,
            range_position=range_position,
            buy_ref=buy_ref,
            sell_ref=sell_ref,
            stop_ref=stop_ref,
            source="twstock.Stock",
        )
    except Exception as exc:  # noqa: BLE001
        return PriceBand(
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            f"error:{exc}",
        )
