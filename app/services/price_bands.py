from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class PriceBand:
    last_close: Optional[float]
    ma5: Optional[float]
    watch_low: Optional[float]
    watch_high: Optional[float]
    source: str


def compute_price_band(code: str) -> PriceBand:
    """Derive a simple observation band from recent OHLCV (not a target price)."""
    try:
        from twstock import Stock

        stock = Stock(code, initial_fetch=True)
        closes = [c for c in stock.close if c is not None]
        lows = [v for v in stock.low if v is not None]
        highs = [v for v in stock.high if v is not None]
        if not closes:
            return PriceBand(None, None, None, None, "empty")

        last_close = float(closes[-1])
        window = min(10, len(closes))
        recent_lows = lows[-window:] or [last_close]
        recent_highs = highs[-window:] or [last_close]
        ma5 = None
        if len(closes) >= 5:
            ma5 = round(sum(closes[-5:]) / 5.0, 2)

        watch_low = round(min(recent_lows), 2)
        watch_high = round(max(recent_highs), 2)
        return PriceBand(last_close, ma5, watch_low, watch_high, "twstock.Stock")
    except Exception as exc:  # noqa: BLE001
        return PriceBand(None, None, None, None, f"error:{exc}")
