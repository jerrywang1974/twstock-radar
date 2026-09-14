import { useEffect, useState } from 'react'
import { api } from '../api'

export default function JobsPage() {
  const [date, setDate] = useState('2026-09-11')
  const [notify, setNotify] = useState(false)
  const [latest, setLatest] = useState<string>('')
  const [result, setResult] = useState('')
  const [error, setError] = useState('')
  const [running, setRunning] = useState(false)

  async function refreshLatest() {
    try {
      const data = await api.jobsLatest()
      setLatest(JSON.stringify(data.job, null, 2))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  useEffect(() => {
    void refreshLatest()
  }, [])

  async function run() {
    setRunning(true)
    setError('')
    setResult('')
    try {
      const data = await api.runJob(date || undefined, notify)
      setResult(JSON.stringify(data, null, 2))
      await refreshLatest()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>任務</h1>
          <p>手動觸發 ingest + 規則掃市；正式環境由 worker 在盤後重試</p>
        </div>
      </div>

      <div className="card">
        <div className="toolbar">
          <div className="field">
            <label>交易日</label>
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
          <label className="muted" style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
            <input
              type="checkbox"
              checked={notify}
              onChange={(e) => setNotify(e.target.checked)}
            />
            同時發送通知
          </label>
          <button className="btn accent" onClick={() => void run()} disabled={running}>
            {running ? '執行中…' : '立即執行'}
          </button>
          <button className="btn" onClick={() => void refreshLatest()}>
            重新讀取最新任務
          </button>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}

      <div className="split-2">
        <div className="card">
          <h2>最新任務</h2>
          <pre className="mono" style={{ whiteSpace: 'pre-wrap', margin: 0 }}>
            {latest || '-'}
          </pre>
        </div>
        <div className="card">
          <h2>本次執行結果</h2>
          <pre className="mono" style={{ whiteSpace: 'pre-wrap', margin: 0 }}>
            {result || '尚未執行'}
          </pre>
        </div>
      </div>
    </div>
  )
}
