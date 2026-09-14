import { useEffect, useState } from 'react'
import { api, lots, type Hit, type InstRow } from '../api'

export default function ScanPage() {
  const [date, setDate] = useState('')
  const [field, setField] = useState('trust_net')
  const [hits, setHits] = useState<Hit[]>([])
  const [rows, setRows] = useState<InstRow[]>([])
  const [tradeDate, setTradeDate] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function load() {
    setLoading(true)
    setError('')
    try {
      const [scan, top] = await Promise.all([
        api.scansToday(date || undefined),
        api.institutionalTop(field, date || undefined),
      ])
      setHits(scan.hits)
      setRows(top.rows)
      setTradeDate(scan.trade_date)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>掃市結果</h1>
          <p>投信／法人排行與規則命中。交易日：{tradeDate || '-'}</p>
        </div>
        <div className="toolbar">
          <div className="field">
            <label>交易日</label>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
          </div>
          <div className="field">
            <label>排行欄位</label>
            <select value={field} onChange={(e) => setField(e.target.value)}>
              <option value="trust_net">投信買賣超</option>
              <option value="foreign_net">外資買賣超</option>
              <option value="dealer_net">自營買賣超</option>
              <option value="total_net">三大法人合計</option>
            </select>
          </div>
          <button className="btn primary" onClick={() => void load()} disabled={loading}>
            查詢
          </button>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}

      <div className="split-2">
        <div className="card">
          <h2>排行（張）</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>代碼</th>
                  <th>名稱</th>
                  <th>市場</th>
                  <th>投信</th>
                  <th>外資</th>
                  <th>合計</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={`${row.market}-${row.code}`}>
                    <td className="mono">{row.code}</td>
                    <td>{row.name}</td>
                    <td>{row.market}</td>
                    <td className={row.trust_net >= 0 ? 'pos' : 'neg'}>{lots(row.trust_net)}</td>
                    <td className={row.foreign_net >= 0 ? 'pos' : 'neg'}>
                      {lots(row.foreign_net)}
                    </td>
                    <td className={row.total_net >= 0 ? 'pos' : 'neg'}>{lots(row.total_net)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!rows.length && !loading && <div className="empty-box">尚無排行資料</div>}
        </div>

        <div className="card">
          <h2>規則命中</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>代碼</th>
                  <th>規則</th>
                  <th>原因</th>
                  <th>標籤</th>
                </tr>
              </thead>
              <tbody>
                {hits.map((hit, idx) => (
                  <tr key={`${hit.code}-${hit.rule_id}-${idx}`}>
                    <td className="mono">
                      {hit.code} {hit.name}
                    </td>
                    <td>{hit.rule_id}</td>
                    <td>{hit.reason}</td>
                    <td>{hit.suggested_action}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!hits.length && !loading && <div className="empty-box">當日尚無規則命中</div>}
        </div>
      </div>
    </div>
  )
}
