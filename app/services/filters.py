from __future__ import annotations

from typing import Iterable, List, Sequence, TypeVar

from app.config import Settings, get_settings

try:
    from twstock.codes import codes as STOCK_CODES
except Exception:  # pragma: no cover
    STOCK_CODES = {}

T = TypeVar("T")

# Keep common equities; drop ETF / warrants / ETN / preferred by default.
ALLOWED_TYPES = {"股票", "創新板"}


def security_type(code: str) -> str | None:
    info = STOCK_CODES.get(code)
    return getattr(info, "type", None) if info else None


def is_tradable_equity(code: str, settings: Settings | None = None) -> bool:
    """Return True if code should be included in scan results."""
    settings = settings or get_settings()
    if not settings.exclude_non_equity:
        return True

    typ = security_type(code)
    if typ is not None:
        return typ in ALLOWED_TYPES

    # Fallback heuristics when codes DB is stale / missing.
    text = str(code).strip()
    if not text.isdigit():
        return False
    if len(text) >= 6:  # typical warrants
        return False
    if text.startswith("00"):  # ETF / index products
        return False
    return len(text) in {4, 5}


def filter_equities(rows: Sequence[T], code_attr: str = "code") -> List[T]:
    return [row for row in rows if is_tradable_equity(getattr(row, code_attr))]


def parse_extra_excludes(raw: str | None) -> set[str]:
    if not raw:
        return set()
    return {part.strip() for part in raw.split(",") if part.strip()}


def apply_exclude_codes(rows: Iterable[T], exclude: set[str], code_attr: str = "code") -> List[T]:
    if not exclude:
        return list(rows)
    return [row for row in rows if getattr(row, code_attr) not in exclude]
