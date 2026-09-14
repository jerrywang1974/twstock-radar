# 使用說明

## CLI

```bash
# 建立資料表
twstock-radar init-db

# 盤後掃市（不發通知）
twstock-radar run --date 2026-09-11 --no-notify

# 掃市並依 .env 發送 Telegram / Email / Slack
twstock-radar run --date 2026-09-11

# 歷史回填（預設不通知；可加 --ingest-only 只抓資料）
twstock-radar backfill --from 2026-09-01 --to 2026-09-11 --sleep 1.5
twstock-radar backfill --from 2026-09-01 --to 2026-09-11 --ingest-only
```

## API

| Method | Path | 說明 |
|--------|------|------|
| GET | `/health` | 健康檢查 |
| GET | `/dashboard` | 今日總覽 |
| POST | `/jobs/run` | 手動 ingest + 規則 + 通知 |
| POST | `/jobs/backfill?from=&to=` | 日期區間回填 |
| GET | `/jobs/latest` | 最近任務 |
| GET | `/scans/today` | 規則命中 |
| GET | `/institutional/top` | 法人排行 |
| GET | `/alerts` | 通知紀錄 |
| GET | `/ai/insights` | AI 觀察（規則命中解讀／價帶） |
| GET | `/settings` | 規則／通道狀態 |
| POST | `/channels/test` | 測試通知通道 |

若設定了 `API_TOKEN`，請帶：

```bash
curl -H "Authorization: Bearer <token>" http://localhost:8000/dashboard
```

## 預設規則

1. **trust_top_buy**：投信買超 ≥ `TRUST_MIN_NET_LOTS` 張，取 Top K  
2. **trust_streak**：投信連買 ≥ `TRUST_STREAK_DAYS` 日  
3. **foreign_trust_align**：外資與投信同向買超  

門檻見 `.env.example`。

## 過濾與冷卻（Phase 3）

- 預設排除非「股票／創新板」（ETF、權證、ETN…）
- `EXCLUDE_CODES=2330,2317` 可再排除指定代碼
- `ALERT_COOLDOWN_DAYS`：同一代碼＋同一規則在冷卻天數內不重複進入通知命中

## AI 觀察（Phase 4）

1. 在 `.env` 設定：
   - `AI_ENABLED=true`
   - `XAI_API_KEY=...`（[console.x.ai](https://console.x.ai)）
   - 可選 `AI_MODEL=grok-4.5`、`AI_MAX_HITS=10`
2. 執行 `twstock-radar run --date YYYY-MM-DD`（或 UI 任務頁）
3. 到「AI 觀察」頁或 `GET /ai/insights` 查看

AI 只解讀「已命中規則」的檔；觀察價帶由近十日行情計算，不是模型空想目標價。內容僅供觀察，非投資建議。

## 資料語意

- 來源：TWSE T86、TPEx 三大法人日報（經 `twstock.institutional`）
- 「投信」= 公開合計，非單家投信／分點
- `broker_detail` 欄位預留，MVP 為空

## 管理介面頁面

- 總覽、掃市、規則、任務、通知紀錄、通道、設定
