import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, lots, type Dashboard } from '../api'

export default function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  async function load() {
    setLoading(true)
    setError('')
    try {
      setData(await api.dashboard())
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const status = data?.job?.status
  const statusClass =
    status === 'success' ? 'ok' : status === 'failed' ? 'bad' : status ? 'warn' : ''

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>今日總覽</h1>
          <p>盤後 ingest 狀態、投信／三大法人淨額與規則命中摘要</p>
        </div>
        <div className="toolbar">
          <button className="btn" onClick={() => void load()} disabled={loading}>
            重新整理
          </button>
          <Link className="btn primary" to="/jobs">
            手動跑任務
          </Link>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}

      <div className="grid stats">
        <div className="card">
          <div className="stat-label">交易日</div>
          <div className="stat-value mono">{data?.trade_date ?? '-'}</div>
        </div>
        <div className="card">
          <div className="stat-label">Ingest</div>
          <div className="stat-value">
            {status ? <span className={`pill ${statusClass}`}>{status}</span> : '-'}
          </div>
        </div>
        <div className="card">
          <div className="stat-label">投信淨額合計（張）</div>
          <div className={`stat-value ${(data?.trust_net_sum ?? 0) >= 0 ? 'pos' : 'neg'}`}>
            {data ? lots(data.trust_net_sum) : '-'}
          </div>
        </div>
        <div className="card">
          <div className="stat-label">規則命中 / 通知</div>
          <div className="stat-value mono">
            {data ? `${data.hit_count} / ${data.alert_count}` : '-'}
          </div>
        </div>
      </div>

      <div className="split-2">
        <div className="card">
          <h2>最近一次任務</h2>
          {!data?.job && <div className="empty-box">尚無任務。到「任務」頁手動執行掃市。</div>}
          {data?.job && (
            <div className="stack">
              <div>
                上市列數：<span className="mono">{data.job.twse_rows}</span>
              </div>
              <div>
                上櫃列數：<span className="mono">{data.job.tpex_rows}</span>
              </div>
              <div className="muted">{data.job.message}</div>
              <div>
                三大法人淨額合計（張）：{' '}
                <span className={`mono ${(data.total_net_sum ?? 0) >= 0 ? 'pos' : 'neg'}`}>
                  {lots(data.total_net_sum)}
                </span>
              </div>
            </div>
          )}
        </div>
        <div className="card">
          <h2>操作捷徑</h2>
          <div className="stack">
            <Link to="/scan">查看掃市排行與命中明細 →</Link>
            <Link to="/channels">檢查 Telegram / Email / Slack 通道 →</Link>
            <Link to="/rules">檢視目前啟用規則 →</Link>
          </div>
        </div>
      </div>
    </div>
  )
}
