const API_BASE = import.meta.env.VITE_API_BASE ?? '/api'

function authHeaders(): HeadersInit {
  const token = localStorage.getItem('radar_api_token') || ''
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...(init?.headers || {}),
    },
  })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `HTTP ${response.status}`)
  }
  return response.json() as Promise<T>
}

export type Dashboard = {
  trade_date: string
  job: null | {
    id: number
    status: string
    twse_rows: number
    tpex_rows: number
    message: string
  }
  hit_count: number
  alert_count: number
  trust_net_sum: number
  total_net_sum: number
}

export type Hit = {
  code: string
  name: string
  rule_id: string
  reason: string
  suggested_action: string
  metrics_json: string
}

export type InstRow = {
  code: string
  name: string
  market: string
  trust_net: number
  foreign_net: number
  dealer_net: number
  total_net: number
}

export type AlertRow = {
  id: number
  trade_date: string
  channel: string
  subject: string
  status: string
  error: string
}

export type Settings = {
  timezone: string
  ingest_retry_times: string
  rules: {
    trust_top_k: number
    trust_streak_days: number
    trust_min_net_lots: number
    alert_cooldown_days: number
  }
  filters?: {
    exclude_non_equity: boolean
    exclude_codes: string
    backfill_sleep_seconds: number
  }
  channels: {
    telegram: boolean
    email: boolean
    slack: boolean
  }
  rules_catalog: Array<{ id: string; name: string; description: string }>
}

export const api = {
  health: () => request<{ status: string; app: string }>('/health'),
  dashboard: () => request<Dashboard>('/dashboard'),
  settings: () => request<Settings>('/settings'),
  scansToday: (tradeDate?: string) =>
    request<{ trade_date: string; hits: Hit[] }>(
      `/scans/today${tradeDate ? `?trade_date=${tradeDate}` : ''}`,
    ),
  institutionalTop: (field = 'trust_net', tradeDate?: string) =>
    request<{ trade_date: string; field: string; rows: InstRow[] }>(
      `/institutional/top?field=${field}${tradeDate ? `&trade_date=${tradeDate}` : ''}`,
    ),
  alerts: () => request<{ alerts: AlertRow[] }>('/alerts'),
  jobsLatest: () =>
    request<{
      job: null | {
        id: number
        trade_date: string
        status: string
        twse_rows: number
        tpex_rows: number
        message: string
      }
    }>('/jobs/latest'),
  runJob: (tradeDate?: string, notify = true) =>
    request<Record<string, unknown>>(
      `/jobs/run?notify=${notify}${tradeDate ? `&trade_date=${tradeDate}` : ''}`,
      { method: 'POST' },
    ),
  testChannels: () =>
    request<{ alerts: AlertRow[] }>('/channels/test', { method: 'POST' }),
  aiInsights: (tradeDate?: string) =>
    request<{
      trade_date: string
      enabled: boolean
      configured: boolean
      insights: Array<{
        code: string
        name: string
        rule_id: string
        rationale: string
        action_bias: string
        watch_low: number | null
        watch_high: number | null
        last_close: number | null
        model: string
      }>
    }>(`/ai/insights${tradeDate ? `?trade_date=${tradeDate}` : ''}`),
}

export function lots(shares: number): string {
  return (shares / 1000).toLocaleString('zh-TW', { maximumFractionDigits: 0 })
}
