import { useEffect, useState } from 'react'
import { api, type Settings } from '../api'

export default function RulesPage() {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .settings()
      .then(setSettings)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
  }, [])

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>規則</h1>
          <p>目前啟用的掃市規則（由環境變數門檻控制，Phase 2 先做檢視）</p>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}

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
    </div>
  )
}
