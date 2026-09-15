# Admin Web (Phase 2)

Vite + React 管理後台（繁中）。

## 開發

先啟動 API（專案根目錄）：

```bash
cd ..
DATABASE_URL=sqlite:///./radar.db .venv/bin/uvicorn app.api.main:app --reload --port 18000
```

再啟動前端：

```bash
npm install
npm run dev
```

瀏覽器開 `http://localhost:5173`。前端透過 Vite proxy 把 `/api/*` 轉到 `http://127.0.0.1:18000`。

## 頁面

- 總覽 / 掃市 / 規則 / 任務 / 通知紀錄 / 通道 / 設定
