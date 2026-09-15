import { useEffect, useState } from 'react'
import { api, getApiToken, setApiToken, type RuleSetting, type Settings } from '../api'

export default function SettingsPage() {
  const [token, setToken] = useState(getApiToken())
  const [settings, setSettings] = useState<Settings | null>(null)
  const [rules, setRules] = useState<RuleSetting[]>([])
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  async function load() {
    setError('')
    try {
      const [s, r] = await Promise.all([api.settings(), api.getRuleSettings()])
      setSettings(s)
      setRules(r.rules)
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

  function patchRule(id: string, patch: Partial<RuleSetting>) {
    setRules((prev) => prev.map((r) => (r.id === id ? { ...r, ...patch } : r)))
  }

  async function saveRules() {
    setSaving(true)
    setError('')
    setMessage('')
    try {
      const payload = rules.map((r) => ({
        rule_id: r.id,
        enabled: r.enabled,
        lookback_days: r.lookback_days,
      }))
      const data = await api.saveRuleSettings(payload)
      setRules(data.rules)
      setMessage(`已儲存 ${data.count} 條掃市規則設定`)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>設定</h1>
          <p>API token、掃市規則開關與觀察天數（1–90+，各規則有上下限）</p>
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
      </div>

      <div className="card">
        <div className="page-head" style={{ marginBottom: '0.75rem' }}>
          <div>
            <h2 style={{ margin: 0 }}>掃市規則範本</h2>
            <p className="muted" style={{ margin: '0.35rem 0 0' }}>
              啟用後才會進入掃市。不含短線新聞衝擊規則；詳見 docs/RULES.md。
            </p>
          </div>
          <button className="btn accent" onClick={() => void saveRules()} disabled={saving}>
            {saving ? '儲存中…' : '儲存規則設定'}
          </button>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>啟用</th>
                <th>規則</th>
                <th>預設</th>
                <th>觀察天數</th>
                <th>用途</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((rule) => (
                <tr key={rule.id}>
                  <td>
                    <input
                      type="checkbox"
                      checked={rule.enabled}
                      onChange={(e) => patchRule(rule.id, { enabled: e.target.checked })}
                    />
                  </td>
                  <td>
                    <div>{rule.name}</div>
                    <div className="mono muted">{rule.id}</div>
                  </td>
                  <td>{rule.default_enabled ? 'ON' : 'OFF'}</td>
                  <td>
                    <input
                      type="number"
                      min={rule.min_lookback_days}
                      max={rule.max_lookback_days}
                      value={rule.lookback_days}
                      disabled={rule.min_lookback_days === rule.max_lookback_days}
                      onChange={(e) =>
                        patchRule(rule.id, {
                          lookback_days: Number(e.target.value),
                        })
                      }
                      style={{ width: 88 }}
                    />
                    <div className="muted">
                      {rule.min_lookback_days}–{rule.max_lookback_days}
                    </div>
                  </td>
                  <td style={{ whiteSpace: 'normal', minWidth: 240 }}>
                    {rule.purpose}
                    {rule.notes ? <div className="muted">{rule.notes}</div> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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
            {settings.ai && (
              <div>
                AI：{settings.ai.enabled ? '開啟' : '關閉'}／模型 {settings.ai.model}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
