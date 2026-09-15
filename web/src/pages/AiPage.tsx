import { useEffect, useState } from 'react'
import { api } from '../api'

type Insight = {
  code: string
  name: string
  rule_id: string
  rationale: string
  action_bias: string
  watch_low: number | null
  watch_high: number | null
  last_close: number | null
  model: string
}

export default function AiPage() {
  const [date, setDate] = useState('2026-09-11')
  const [insights, setInsights] = useState<Insight[]>([])
  const [meta, setMeta] = useState({ enabled: false, configured: false, trade_date: '' })
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [running, setRunning] = useState(false)

  async function load() {
    setLoading(true)
    setError('')
    try {
      const data = await api.aiInsights(date || undefined)
      setInsights(data.insights)
      setMeta({
        enabled: data.enabled,
        configured: data.configured,
        trade_date: data.trade_date,
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  async function runAnalyze() {
    setRunning(true)
    setError('')
    setMessage('')
    try {
      const data = await api.aiAnalyze(date || undefined)
      setInsights(data.insights)
      setMeta((prev) => ({ ...prev, trade_date: data.trade_date }))
      setMessage(`已完成 AI 分析 ${data.count} 檔（交易日 ${data.trade_date}）`)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setRunning(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>AI 觀察</h1>
          <p>
            對規則命中做 LLM 解讀與觀察價帶（非投資建議）。交易日：
            {meta.trade_date || '-'}
          </p>
        </div>
        <div className="toolbar">
          <div className="field">
            <label>交易日</label>
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
          <button className="btn" onClick={() => void load()} disabled={loading || running}>
            查詢
          </button>
          <button
            className="btn accent"
            onClick={() => void runAnalyze()}
            disabled={running || !meta.enabled || !meta.configured}
          >
            {running ? '分析中…' : '執行 AI 分析'}
          </button>
        </div>
      </div>

      <div className="grid stats">
        <div className="card">
          <div className="stat-label">AI 開關</div>
          <div className="stat-value">
            <span className={`pill ${meta.enabled ? 'ok' : 'warn'}`}>
              {meta.enabled ? 'enabled' : 'disabled'}
            </span>
          </div>
        </div>
        <div className="card">
          <div className="stat-label">XAI_API_KEY</div>
          <div className="stat-value">
            <span className={`pill ${meta.configured ? 'ok' : 'warn'}`}>
              {meta.configured ? '已設定' : '未設定'}
            </span>
          </div>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}
      {message && <div className="ok-box">{message}</div>}
      {!meta.enabled && (
        <div className="empty-box">
          在 `.env` 設定 `AI_ENABLED=true` 與 `XAI_API_KEY=...` 後重啟 API，即可執行分析。
        </div>
      )}
      {meta.enabled && !meta.configured && (
        <div className="empty-box">已開啟 AI，但仍缺少 `XAI_API_KEY`。</div>
      )}

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>代碼</th>
                <th>規則</th>
                <th>偏向</th>
                <th>收盤</th>
                <th>觀察區間</th>
                <th>說明</th>
              </tr>
            </thead>
            <tbody>
              {insights.map((row, idx) => (
                <tr key={`${row.code}-${row.rule_id}-${idx}`}>
                  <td className="mono">
                    {row.code} {row.name}
                  </td>
                  <td>{row.rule_id}</td>
                  <td>{row.action_bias}</td>
                  <td className="mono">{row.last_close ?? '-'}</td>
                  <td className="mono">
                    {row.watch_low != null && row.watch_high != null
                      ? `${row.watch_low} - ${row.watch_high}`
                      : '-'}
                  </td>
                  <td style={{ whiteSpace: 'normal', minWidth: 280 }}>{row.rationale}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!insights.length && !loading && !running && (
          <div className="empty-box">尚無 AI 觀察資料。可按「執行 AI 分析」產生。</div>
        )}
      </div>
    </div>
  )
}
