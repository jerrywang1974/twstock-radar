# Changelog

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
