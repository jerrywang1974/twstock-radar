import { NavLink, Route, Routes } from 'react-router-dom'
import AlertsPage from './pages/AlertsPage'
import ChannelsPage from './pages/ChannelsPage'
import DashboardPage from './pages/DashboardPage'
import JobsPage from './pages/JobsPage'
import RulesPage from './pages/RulesPage'
import ScanPage from './pages/ScanPage'
import SettingsPage from './pages/SettingsPage'

const links = [
  { to: '/', label: '總覽', end: true },
  { to: '/scan', label: '掃市' },
  { to: '/rules', label: '規則' },
  { to: '/jobs', label: '任務' },
  { to: '/alerts', label: '通知紀錄' },
  { to: '/channels', label: '通道' },
  { to: '/settings', label: '設定' },
]

export default function App() {
  return (
    <div className="app-shell">
      <aside className="side">
        <div className="brand">
          <strong>twstock-radar</strong>
          <span>法人掃市控制台</span>
        </div>
        <nav className="nav">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              className={({ isActive }) => (isActive ? 'active' : undefined)}
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
        <div className="side-foot">
          規則命中僅供觀察，不構成投資建議。AI 解讀仍在後期佇列。
        </div>
      </aside>
      <main className="main">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/scan" element={<ScanPage />} />
          <Route path="/rules" element={<RulesPage />} />
          <Route path="/jobs" element={<JobsPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/channels" element={<ChannelsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  )
}
