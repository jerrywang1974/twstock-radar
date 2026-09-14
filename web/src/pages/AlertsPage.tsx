import { useEffect, useState } from 'react'
import { api, type AlertRow } from '../api'

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<AlertRow[]>([])
  const [error, setError] = useState('')

  async function load() {
    setError('')
    try {
      const data = await api.alerts()
      setAlerts(data.alerts)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  useEffect(() => {
    void load()
  }, [])

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>通知紀錄</h1>
          <p>Telegram / Email / Slack 發送結果與錯誤訊息</p>
        </div>
        <button className="btn" onClick={() => void load()}>
          重新整理
        </button>
      </div>

      {error && <div className="error-box">{error}</div>}

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>日期</th>
                <th>通道</th>
                <th>主旨</th>
                <th>狀態</th>
                <th>錯誤</th>
              </tr>
            </thead>
            <tbody>
              {alerts.map((alert) => (
                <tr key={alert.id}>
                  <td className="mono">{alert.id}</td>
                  <td className="mono">{alert.trade_date}</td>
                  <td>{alert.channel}</td>
                  <td>{alert.subject}</td>
                  <td>
                    <span
                      className={`pill ${
                        alert.status === 'sent'
                          ? 'ok'
                          : alert.status === 'failed'
                            ? 'bad'
                            : 'warn'
                      }`}
                    >
                      {alert.status}
                    </span>
                  </td>
                  <td className="muted">{alert.error || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!alerts.length && <div className="empty-box">尚無通知紀錄</div>}
      </div>
    </div>
  )
}
