# 使用說明

## CLI

```bash
# 建立資料表
twstock-radar init-db

# 盤後掃市（不發通知）
twstock-radar run --date 2026-09-11 --no-notify

# 掃市並依 .env 發送 Telegram / Email / Slack
twstock-radar run --date 2026-09-11
```

## API

| Method | Path | 說明 |
|--------|------|------|
| GET | `/health` | 健康檢查 |
| GET | `/dashboard` | 今日總覽 |
| POST | `/jobs/run` | 手動 ingest + 規則 + 通知 |
| GET | `/jobs/latest` | 最近任務 |
| GET | `/scans/today` | 規則命中 |
| GET | `/institutional/top` | 法人排行 |
| GET | `/alerts` | 通知紀錄 |
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

## 資料語意

- 來源：TWSE T86、TPEx 三大法人日報（經 `twstock.institutional`）
- 「投信」= 公開合計，非單家投信／分點
- `broker_detail` 欄位預留，MVP 為空

## 管理介面頁面

- 總覽、掃市、規則、任務、通知紀錄、通道、設定
