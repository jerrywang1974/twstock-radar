# Changelog

## 0.4.0 — 2026-09-15

### Added
- Rule template catalog with enable/disable + lookback (1–90 days, per-rule bounds).
- Additional chip-flow templates (foreign top/streak, diverge, dual overlap, turn, cumulative, crowded fade).
- Settings UI/API to toggle rules; `docs/RULES.md` documents purpose and default on/off.
- No short-term news-impact rules in the default template set.

## 0.3.4 — 2026-09-15

### Added
- AI rule-idea generator for operator reference (`rule-ideas` CLI, `/rules/ideas*`, Rules UI).
- Built-in fallback rule templates when AI is off/unavailable.
- Ideas are stored per trade date and never auto-enabled in the scanner.

## 0.3.3 — 2026-09-15

### Docs
- Add `docs/AI_NOTES.md` describing action commands, objective refs, and design constraints.
- Add module/field comments in `ai_analysis.py`, `price_bands.py`, and `AiInsight`.

## 0.3.2 — 2026-09-15

### Added
- Clear AI action commands: `BUY`, `WAIT_PULLBACK`, `HOLD`, `REDUCE`, `SELL`, `AVOID`, `BREAKOUT_WATCH`.
- `action_plan` checklist plus objective `buy_ref` / `sell_ref` / `stop_ref` from recent OHLCV.
- Admin AI page highlights command and reference prices.

## 0.3.1 — 2026-09-15

### Changed
- Default `AI_MAX_HITS` raised to 15; ranking prefers better upside/downside ratio.
- AI prompt is risk-first and growth-aware (`risk_level`, `growth_score`, avoid/growth thesis).
- Quant overlays: near range-high or poor reward/risk can downgrade `buy_bias`.
- Admin AI table shows risk, growth score, and upside/downside %.

## 0.3.0 — 2026-09-14

### Added
- Phase 4 AI observations via SpaceXAI/xAI (`XAI_API_KEY`, `AI_ENABLED`).
- Quant price observation bands from recent OHLCV (`watch_low` / `watch_high`).
- `GET /ai/insights` and Admin UI page「AI 觀察」.
- Docker edge profile now builds Vite UI into nginx (`deploy/Dockerfile.web`), proxying `/api` to backend.

### Notes
- AI text is interpretive only; bands are derived from market data, not model-invented targets.
- Disclaimer remains in digests and UI.

## 0.2.0 — 2026-09-14

### Added
- Historical backfill: `twstock-radar backfill --from/--to` and `POST /jobs/backfill`.
- Equity filter: exclude ETF / warrants / ETN by default (`EXCLUDE_NON_EQUITY`).
- Extra exclude list via `EXCLUDE_CODES`.
- Alert cooldown for repeated code+rule hits (`ALERT_COOLDOWN_DAYS`).

### Changed
- Scan / institutional top rankings now apply equity filters.
- Digest copy notes that filters and cooldown are applied.

## 0.1.0 — 2026-09-14

### Added
- Institutional market ingest via `twstock.institutional` (TWSE T86 + TPEx).
- Rule engine: trust top buy, trust streak, foreign/trust alignment.
- Notifiers: Telegram, Email (SMTP), Slack webhook.
- FastAPI endpoints for dashboard, jobs, scans, alerts, settings, channel test.
- APScheduler worker with weekday after-close retries (Asia/Taipei).
- Docker: full Postgres stack, SQLite test compose, optional nginx `edge` profile.
- Vite + React admin UI (總覽 / 掃市 / 規則 / 任務 / 通知 / 通道 / 設定).
- Docs: `docs/USAGE.md`, `docs/DEPLOY.md`.

### Notes
- “投信” uses public **aggregate** trust flow; per-broker detail is reserved (`broker_detail`).
- AI recommendation / pricing remains queued for a later phase.
- Depends on twstock PR: https://github.com/jerrywang1974/twstock/pull/1
