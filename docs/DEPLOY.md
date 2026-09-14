# 部署指南（Docker / VPS）

## 架構摘要

| 元件 | 說明 |
|------|------|
| `api` | FastAPI（掃市結果、任務、通知測試） |
| `worker` | 盤後排程（預設 18:30 / 19:30 / 20:30 Asia/Taipei） |
| `db` | Postgres 16（完整堆疊） |
| `web` | 可選（compose profile `edge`）：Vite 靜態檔 + nginx，`/api` 反代到 API |
| 本機 `web/` | 開發用 `npm run dev`（proxy 到 :8000） |

相依函式庫：本機旁的 [`twstock`](https://github.com/jerrywang1974/twstock)（需含 `twstock.institutional`）。

## 建置注意

Docker build context 必須是**同時包含**兩個目錄的上一層：

```text
parent/
  twstock/           # 函式庫
  twstock-radar/     # 本專案
```

在 `twstock-radar/` 內執行 compose 時，`dockerfile` 會用 `context: ..`。

## 本機／測試

### SQLite 單容器

```bash
cd twstock-radar
cp -n .env.example .env
docker compose -f docker-compose.sqlite.yml up -d --build
curl http://localhost:8000/health
docker compose -f docker-compose.sqlite.yml exec api \
  twstock-radar run --date 2026-09-11 --no-notify
```

### Postgres 完整堆疊

```bash
cp -n .env.example .env
# 填入通知相關變數（可選）
docker compose up -d --build
curl http://localhost:8000/health
curl -X POST 'http://localhost:8000/jobs/run?trade_date=2026-09-11&notify=false'
```

## VPS 建議步驟

1. 安裝 Docker Engine + Compose plugin  
2. clone `twstock` 與 `twstock-radar` 到同一父目錄  
3. `cp .env.example .env`，設定：
   - `API_TOKEN`
   - `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`
   - `SMTP_*`（Email）
   - `SLACK_WEBHOOK_URL`
4. `docker compose up -d --build`
5. （可選）啟用前端 + nginx：
   ```bash
   docker compose --profile edge up -d --build
   # http://localhost        -> Admin UI
   # http://localhost/api/*  -> FastAPI
   ```
6. 若要用 AI：在 `.env` 設 `AI_ENABLED=true` 與 `XAI_API_KEY`
7. 網域 A 記錄指向 VPS 後，用 certbot webroot 簽憑證到 `deploy/certbot/conf`，再補 443 server block

## 管理後台

開發：

```bash
cd web
npm install
npm run dev
# http://localhost:5173  （/api 代理到 :8000）
```

正式（Docker edge profile）會把前端建進 nginx image。

## 驗收清單

- [ ] `GET /health` 回 `ok`
- [ ] `POST /jobs/run?notify=false` 得到 `status=success` 且 twse/tpex rows > 0
- [ ] 「通道」測試發送成功（至少一個通道）
- [ ] 交易日盤後 worker 有產生 `ingest_jobs` 紀錄

## 免責

規則命中與通知內容僅供觀察，不構成投資建議。
