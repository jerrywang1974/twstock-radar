"""Load/update per-rule enable + lookback settings from templates defaults."""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RuleConfig
from app.rules.templates import RULE_TEMPLATES, get_template, list_templates


def ensure_rule_configs(db: Session) -> list[RuleConfig]:
    """Insert missing template rows with catalog defaults."""
    existing = {
        row.rule_id: row for row in db.scalars(select(RuleConfig)).all()
    }
    changed = False
    for tmpl in RULE_TEMPLATES:
        if tmpl.id in existing:
            continue
        db.add(
            RuleConfig(
                rule_id=tmpl.id,
                enabled=1 if tmpl.default_enabled else 0,
                lookback_days=tmpl.default_lookback_days,
                updated_at=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None),
            )
        )
        changed = True
    if changed:
        db.commit()
    return list(db.scalars(select(RuleConfig)).all())


def _clamp_lookback(rule_id: str, lookback_days: int) -> int:
    tmpl = get_template(rule_id)
    if not tmpl:
        return max(1, int(lookback_days))
    value = int(lookback_days)
    return max(tmpl.min_lookback_days, min(tmpl.max_lookback_days, value))


def list_rule_settings(db: Session) -> list[dict[str, Any]]:
    ensure_rule_configs(db)
    configs = {c.rule_id: c for c in db.scalars(select(RuleConfig)).all()}
    out: list[dict[str, Any]] = []
    for tmpl in RULE_TEMPLATES:
        cfg = configs.get(tmpl.id)
        enabled = bool(cfg.enabled) if cfg else tmpl.default_enabled
        lookback = cfg.lookback_days if cfg else tmpl.default_lookback_days
        out.append(
            {
                **tmpl.as_dict(),
                "enabled": enabled,
                "lookback_days": lookback,
            }
        )
    return out


def get_enabled_rule_map(db: Session) -> dict[str, dict[str, Any]]:
    """rule_id -> {enabled, lookback_days, template...} for scanner."""
    return {
        item["id"]: item
        for item in list_rule_settings(db)
        if item.get("enabled")
    }


def update_rule_settings(
    db: Session, updates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    ensure_rule_configs(db)
    by_id = {c.rule_id: c for c in db.scalars(select(RuleConfig)).all()}
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    for item in updates:
        rule_id = str(item.get("rule_id") or item.get("id") or "")
        tmpl = get_template(rule_id)
        if not tmpl:
            continue
        cfg = by_id.get(rule_id)
        if not cfg:
            cfg = RuleConfig(rule_id=rule_id)
            db.add(cfg)
            by_id[rule_id] = cfg
        if "enabled" in item:
            cfg.enabled = 1 if bool(item["enabled"]) else 0
        if "lookback_days" in item and item["lookback_days"] is not None:
            cfg.lookback_days = _clamp_lookback(rule_id, int(item["lookback_days"]))
        cfg.updated_at = now
    db.commit()
    return list_rule_settings(db)


def catalog_for_api(db: Session) -> list[dict[str, Any]]:
    """Templates merged with runtime settings (for /settings)."""
    return list_rule_settings(db)
