import { useEffect, useState } from 'react'
import { api, getApiToken, setApiToken, type Settings } from '../api'

export default function SettingsPage() {
  const [token, setToken] = useState(getApiToken())
  const [settings, setSettings] = useState<Settings | null>(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function load() {
    setError('')
    try {
      setSettings(await api.settings())
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  useEffect(() => {
    void load()
  }, [])

  function saveToken() {
    setApiToken(token)
    setMessage('API token 已存到瀏覽器 localStorage')
    void load()
  }

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>設定</h1>
          <p>瀏覽器 API token、時區與排程資訊</p>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}
      {message && <div className="ok-box">{message}</div>}

      <div className="card">
        <h2>API Token</h2>
        <div className="toolbar">
          <div className="field" style={{ flex: 1 }}>
            <label>Bearer token（若後端設了 API_TOKEN）</label>
            <input
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="需與 .env 的 API_TOKEN 相同（本機預設 change-me）"
              style={{ width: '100%' }}
            />
          </div>
          <button className="btn primary" onClick={saveToken}>
            儲存
          </button>
        </div>
        <p className="muted" style={{ marginTop: '0.75rem' }}>
          若看到 Unauthorized，把這裡改成與伺服器 `.env` 裡 `API_TOKEN` 一致後儲存，再回總覽重新整理。
        </p>
      </div>

      <div className="card">
        <h2>伺服器設定</h2>
        {!settings && <div className="empty-box">讀取中或無法連線</div>}
        {settings && (
          <div className="stack">
            <div>時區：{settings.timezone}</div>
            <div>盤後重試：{settings.ingest_retry_times}</div>
            <div>
              通道：Telegram {settings.channels.telegram ? '✓' : '✗'} / Email{' '}
              {settings.channels.email ? '✓' : '✗'} / Slack{' '}
              {settings.channels.slack ? '✓' : '✗'}
            </div>
            {settings.filters && (
              <>
                <div>
                  排除非股票：{settings.filters.exclude_non_equity ? '是' : '否'}
                </div>
                <div>額外排除代碼：{settings.filters.exclude_codes || '(無)'}</div>
                <div>回填間隔秒數：{settings.filters.backfill_sleep_seconds}</div>
              </>
            )}
            {settings.ai && (
              <>
                <div>
                  AI：{settings.ai.enabled ? '開啟' : '關閉'}
                  {settings.ai.configured ? '（已設定 key）' : '（未設定 key）'}
                </div>
                <div>
                  模型：{settings.ai.model}／每次最多 {settings.ai.max_hits} 檔
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
