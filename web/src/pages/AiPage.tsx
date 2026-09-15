import { useEffect, useState } from 'react'
import { api } from '../api'

type Insight = {
  code: string
  name: string
  rule_id: string
  rationale: string
  action_bias: string
  action_command?: string
  action_plan?: string
  risk_level?: string
  growth_score?: number | null
  upside_pct?: number | null
  downside_pct?: number | null
  avoid_reason?: string
  growth_thesis?: string
  buy_ref?: number | null
  sell_ref?: number | null
  stop_ref?: number | null
  watch_low: number | null
  watch_high: number | null
  last_close: number | null
  model: string
}

function riskClass(level?: string): string {
  if (level === 'avoid' || level === 'high') return 'bad'
  if (level === 'medium') return 'warn'
  if (level === 'low') return 'ok'
  return ''
}

function commandClass(cmd?: string): string {
  if (!cmd) return ''
  if (cmd === 'BUY' || cmd === 'BREAKOUT_WATCH') return 'ok'
  if (cmd === 'SELL' || cmd === 'AVOID' || cmd === 'REDUCE') return 'bad'
  return 'warn'
}

export default function AiPage() {
  const [date, setDate] = useState('2026-09-11')
  const [insights, setInsights] = useState<Insight[]>([])
  const [meta, setMeta] = useState({
    enabled: false,
    configured: false,
    trade_date: '',
    max_hits: 15,
  })
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
        max_hits: data.max_hits ?? 15,
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
      setMessage(
        `已完成 AI 操作計畫 ${data.count} 檔（含買賣參考價；交易日 ${data.trade_date}）`,
      )
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
          <h1>AI 觀察／操作計畫</h1>
          <p>
            清楚訊號：BUY / WAIT_PULLBACK / HOLD / REDUCE / SELL / AVOID，並附客觀參考價（非投資建議）。
            交易日：{meta.trade_date || '-'}／每次最多 {meta.max_hits} 檔
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
            {running ? '分析中（可能需數分鐘）…' : '執行 AI 分析'}
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

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>代碼</th>
                <th>操作指令</th>
                <th>參考買／賣／停</th>
                <th>風險</th>
                <th>成長分</th>
                <th>行動計畫</th>
                <th>說明</th>
              </tr>
            </thead>
            <tbody>
              {insights.map((row, idx) => (
                <tr key={`${row.code}-${row.rule_id}-${idx}`}>
                  <td className="mono">
                    {row.code} {row.name}
                    <div className="muted">收 {row.last_close ?? '-'}</div>
                  </td>
                  <td>
                    <span className={`pill ${commandClass(row.action_command)}`}>
                      {row.action_command || '-'}
                    </span>
                  </td>
                  <td className="mono">
                    {row.buy_ref ?? '-'} / {row.sell_ref ?? '-'} / {row.stop_ref ?? '-'}
                  </td>
                  <td>
                    <span className={`pill ${riskClass(row.risk_level)}`}>
                      {row.risk_level || '-'}
                    </span>
                  </td>
                  <td className="mono">{row.growth_score ?? '-'}</td>
                  <td style={{ whiteSpace: 'pre-wrap', minWidth: 220 }}>
                    {row.action_plan || '-'}
                  </td>
                  <td style={{ whiteSpace: 'normal', minWidth: 260 }}>{row.rationale}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!insights.length && !loading && !running && (
          <div className="empty-box">尚無資料。按「執行 AI 分析」產生操作指令與參考價。</div>
        )}
      </div>
    </div>
  )
}
