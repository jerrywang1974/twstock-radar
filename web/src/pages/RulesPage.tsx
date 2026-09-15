import { useEffect, useState } from 'react'
import { api, type Settings } from '../api'

type RuleIdea = {
  id: number
  trade_date: string
  idea_id: string
  title: string
  logic: string
  why: string
  data_needed: string
  risk_notes: string
  priority: string
  example_codes: string
  model: string
}

function priorityClass(p: string): string {
  if (p === 'high') return 'ok'
  if (p === 'low') return 'warn'
  return ''
}

export default function RulesPage() {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [ideas, setIdeas] = useState<RuleIdea[]>([])
  const [date, setDate] = useState('2026-09-11')
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)

  async function loadSettings() {
    try {
      setSettings(await api.settings())
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  async function loadIdeas() {
    setLoading(true)
    setError('')
    try {
      const data = await api.ruleIdeas(date || undefined)
      setIdeas(data.ideas)
      setNote(data.note || '')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  async function generate(useAi: boolean) {
    setGenerating(true)
    setError('')
    setMessage('')
    try {
      const data = await api.generateRuleIdeas(date || undefined, useAi)
      setIdeas(data.ideas)
      setNote(data.note || '')
      setMessage(
        `已產生 ${data.count} 條規則構想（${useAi ? 'AI' : '內建範本'}／${data.trade_date}）`,
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setGenerating(false)
    }
  }

  useEffect(() => {
    void loadSettings()
    void loadIdeas()
  }, [])

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>規則</h1>
          <p>上方是目前啟用規則；下方可用 AI 產生更多構想，僅供你參考筆記，不會自動上線。</p>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}
      {message && <div className="ok-box">{message}</div>}

      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))' }}>
        {(settings?.rules_catalog || []).map((rule) => (
          <div className="card" key={rule.id}>
            <h3>{rule.name}</h3>
            <div className="mono muted" style={{ marginBottom: '0.6rem' }}>
              {rule.id}
            </div>
            <p style={{ margin: 0 }}>{rule.description}</p>
          </div>
        ))}
      </div>

      {settings && (
        <div className="card">
          <h2>門檻參數</h2>
          <div className="stack">
            <div>投信 Top K：{settings.rules.trust_top_k}</div>
            <div>投信連買天數：{settings.rules.trust_streak_days}</div>
            <div>投信最小買超（張）：{settings.rules.trust_min_net_lots}</div>
            <div>通知冷卻天數：{settings.rules.alert_cooldown_days}</div>
          </div>
        </div>
      )}

      <div className="card">
        <div className="page-head" style={{ marginBottom: '0.75rem' }}>
          <div>
            <h2 style={{ margin: 0 }}>AI 規則構想（參考用）</h2>
            <p className="muted" style={{ margin: '0.35rem 0 0' }}>
              {note || '產生後可複製 logic／why 當自己的選股筆記。'}
            </p>
          </div>
          <div className="toolbar">
            <div className="field">
              <label>交易日</label>
              <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
            <button className="btn" onClick={() => void loadIdeas()} disabled={loading || generating}>
              查詢
            </button>
            <button
              className="btn accent"
              onClick={() => void generate(true)}
              disabled={generating}
            >
              {generating ? '產生中…' : 'AI 產生構想'}
            </button>
            <button className="btn" onClick={() => void generate(false)} disabled={generating}>
              載入內建範本
            </button>
          </div>
        </div>

        <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))' }}>
          {ideas.map((idea) => (
            <div className="card" key={`${idea.id}-${idea.idea_id}`}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem' }}>
                <h3 style={{ margin: 0 }}>{idea.title}</h3>
                <span className={`pill ${priorityClass(idea.priority)}`}>{idea.priority}</span>
              </div>
              <div className="mono muted" style={{ margin: '0.4rem 0' }}>
                {idea.idea_id}
              </div>
              <p>
                <strong>條件：</strong>
                {idea.logic}
              </p>
              <p>
                <strong>為什麼：</strong>
                {idea.why}
              </p>
              <p className="muted">
                <strong>資料：</strong>
                {idea.data_needed}
              </p>
              <p className="muted">
                <strong>風險：</strong>
                {idea.risk_notes}
              </p>
              {idea.example_codes && (
                <p className="mono">
                  <strong>例子：</strong>
                  {idea.example_codes}
                </p>
              )}
            </div>
          ))}
        </div>
        {!ideas.length && !loading && !generating && (
          <div className="empty-box">尚無構想。可按「AI 產生構想」或「載入內建範本」。</div>
        )}
      </div>
    </div>
  )
}
