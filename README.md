# twstock-radar

台股三大法人／投信合計掃市、規則命中與通知平台。

依賴旁邊的 [`twstock`](https://github.com/jerrywang1974/twstock) 函式庫（需含 `twstock.institutional`）。

## 文件

- [使用說明](docs/USAGE.md)
- [AI 操作指令／參考價註記](docs/AI_NOTES.md)
- [部署指南（Docker / VPS）](docs/DEPLOY.md)
- [管理後台](web/README.md)
- [Changelog](CHANGELOG.md)

## 快速開關 AI

```bash
# .env
AI_ENABLED=true
XAI_API_KEY=xai-...
AI_MODEL=grok-4.5
```

然後跑掃市；結果見 UI「AI 觀察」或 `GET /ai/insights`。

## 功能（Phase 1）

- 盤後 ingest TWSE T86 + TPEx 法人日報
- 規則：投信買超 Top K、投信連買 N 日、外資+投信同向
- 通知：Telegram / Email / Slack
- API：`/health`、`/jobs/run`、`/scans/today`、`/alerts`
- Worker：週一到五 18:30 / 19:30 / 20:30（Asia/Taipei）重試
- 部署：Docker Compose + nginx（Let’s Encrypt 目錄已預留）

## 本機快速開始

```bash
cd twstock-radar
python3 -m venv .venv
source .venv/bin/activate
pip install -e ../twstock
pip install -e .
cp .env.example .env

# 初始化並手動跑（先不通知）
twstock-radar init-db
twstock-radar run --date 2026-09-11 --no-notify

# API
uvicorn app.api.main:app --reload --port 8000

# Admin UI (另開一個終端)
cd web && npm install && npm run dev
# 開啟 http://localhost:5173
```

## Docker（測試 / 部署）

> 建置 context 是**上一層目錄**（需同時看到 `twstock/` 與 `twstock-radar/`）。

### A. 最輕量測試（單容器 + SQLite）

```bash
cd twstock-radar
cp -n .env.example .env
docker compose -f docker-compose.sqlite.yml up -d --build
curl http://localhost:8000/health
docker compose -f docker-compose.sqlite.yml exec api \
  twstock-radar run --date 2026-09-11 --no-notify
```

### B. 完整堆疊（API + Worker + Postgres）

```bash
cd twstock-radar
cp -n .env.example .env
# 可選：填 TELEGRAM_* / SMTP_* / SLACK_WEBHOOK_URL / API_TOKEN
docker compose up -d --build
curl http://localhost:8000/health
curl -X POST 'http://localhost:8000/jobs/run?trade_date=2026-09-11&notify=false'
```

### C. 加上 nginx（VPS / HTTPS 預留）

```bash
docker compose --profile edge up -d --build
# http://localhost  -> nginx -> api:8000
```

HTTPS（nginx + Let’s Encrypt）建議流程：

1. 把網域 A 記錄指到 VPS
2. 先用 HTTP 啟動（profile `edge`）
3. 用 certbot webroot 簽憑證到 `deploy/certbot/conf`
4. 補上 443 server block 後 reload nginx

只建 image、不啟動：

```bash
cd twstock-radar
docker build -f Dockerfile -t twstock-radar:local ..
```

## 免責

規則命中與通知內容僅供觀察，不構成投資建議。
