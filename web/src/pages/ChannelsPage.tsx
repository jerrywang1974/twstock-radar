import { useEffect, useState } from 'react'
import { api, type AlertRow, type Settings } from '../api'

export default function ChannelsPage() {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [result, setResult] = useState<AlertRow[]>([])
  const [error, setError] = useState('')
  const [testing, setTesting] = useState(false)

  useEffect(() => {
    api
      .settings()
      .then(setSettings)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
  }, [])

  async function test() {
    setTesting(true)
    setError('')
    try {
      const data = await api.testChannels()
      setResult(data.alerts)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setTesting(false)
    }
  }

  const channels = settings?.channels

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>通知通道</h1>
          <p>通道啟用狀態來自伺服器環境變數；憑證請在 `.env` 設定</p>
        </div>
        <button className="btn accent" onClick={() => void test()} disabled={testing}>
          {testing ? '測試中…' : '測試發送'}
        </button>
      </div>

      {error && <div className="error-box">{error}</div>}

      <div className="grid stats">
        {(['telegram', 'email', 'slack'] as const).map((name) => (
          <div className="card" key={name}>
            <div className="stat-label">{name}</div>
            <div className="stat-value">
              <span className={`pill ${channels?.[name] ? 'ok' : 'warn'}`}>
                {channels?.[name] ? '已設定' : '未設定'}
              </span>
            </div>
          </div>
        ))}
        <div className="card">
          <div className="stat-label">設定位置</div>
          <div className="muted" style={{ marginTop: '0.5rem' }}>
            `twstock-radar/.env`
          </div>
        </div>
      </div>

      <div className="card">
        <h2>測試結果</h2>
        {!result.length && <div className="empty-box">尚未測試</div>}
        {!!result.length && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>通道</th>
                  <th>狀態</th>
                  <th>錯誤</th>
                </tr>
              </thead>
              <tbody>
                {result.map((row) => (
                  <tr key={row.id}>
                    <td>{row.channel}</td>
                    <td>{row.status}</td>
                    <td className="muted">{row.error || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
