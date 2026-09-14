import { useEffect, useState } from 'react'
import { api, type Settings } from '../api'

export default function SettingsPage() {
  const [token, setToken] = useState(localStorage.getItem('radar_api_token') || '')
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
    localStorage.setItem('radar_api_token', token.trim())
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
              placeholder="可留空（本機開發預設不強制）"
              style={{ width: '100%' }}
            />
          </div>
          <button className="btn primary" onClick={saveToken}>
            儲存
          </button>
        </div>
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
          </div>
        )}
      </div>
    </div>
  )
}
