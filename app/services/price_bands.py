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
    range_position: Optional[float]  # 0=at low, 1=at high
    source: str

    def as_prompt_dict(self) -> dict:
        return asdict(self)


def _pct(numer: float, denom: float) -> Optional[float]:
    if denom == 0:
        return None
    return round((numer / denom) * 100.0, 2)


def compute_price_band(code: str) -> PriceBand:
    """Derive observation band + upside/downside ratios from recent OHLCV."""
    empty = PriceBand(
        None, None, None, None, None, None, None, None, None, "empty"
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
            source="twstock.Stock",
        )
    except Exception as exc:  # noqa: BLE001
        return PriceBand(
            None, None, None, None, None, None, None, None, None, f"error:{exc}"
        )
