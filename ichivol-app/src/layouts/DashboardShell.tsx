import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { AgentChat } from '../components/AgentChat'
import { NotificationBell } from '../components/NotificationBell'
import {
  IconBacktests,
  IconChevronLeft,
  IconDecisions,
  IconGlobe,
  IconJournal,
  IconMarket,
  IconOverview,
  IconPaper,
  IconSettings,
  IconWatchlist,
} from '../components/NavIcons'
import { ThemeToggle } from '../components/ThemeToggle'
import { getMe, logout } from '../lib/auth'
import { AgentSessionProvider } from '../lib/agentSession'
import { llmStatusLabel, LlmStatusProvider, useLlmStatus } from '../lib/llmStatus'
import { MarketSnapshotProvider } from '../lib/marketSnapshot'

const SIDEBAR_KEY = 'ichivol_sidebar_collapsed'

const NAV_ITEMS = [
  { to: '/app/overview', label: 'Overview', Icon: IconOverview },
  { to: '/app/market', label: 'Marché', Icon: IconMarket },
  { to: '/app/context', label: 'Contexte', Icon: IconGlobe },
  { to: '/app/decisions', label: 'Décisions', Icon: IconDecisions },
  { to: '/app/journal', label: 'Journal', Icon: IconJournal },
  { to: '/app/watchlist', label: 'Watchlist', Icon: IconWatchlist },
  { to: '/app/paper', label: 'Paper', Icon: IconPaper },
  { to: '/app/backtests', label: 'Backtests', Icon: IconBacktests },
  { to: '/app/settings', label: 'Settings', Icon: IconSettings },
]

function LlmHeaderBadge() {
  const { state, provider, model, message, refresh } = useLlmStatus()
  const label = llmStatusLabel(state)
  const detail =
    state === 'ok' && provider && model
      ? `${provider} · ${model}`
      : message || label

  return (
    <button
      type="button"
      className={`llm-status-badge is-${state}`}
      title={detail}
      onClick={() => void refresh()}
      aria-label={detail}
    >
      <span className="llm-status-dot" aria-hidden />
      <span className="llm-status-text">{label}</span>
    </button>
  )
}

function DashboardShellInner() {
  const navigate = useNavigate()
  const llm = useLlmStatus()
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(SIDEBAR_KEY) === '1')
  const [email, setEmail] = useState<string | null>(null)
  const [userMenuOpen, setUserMenuOpen] = useState(false)

  useEffect(() => {
    getMe().then((user) => setEmail(user?.email ?? null))
  }, [])

  function toggleCollapsed() {
    setCollapsed((v) => {
      const next = !v
      localStorage.setItem(SIDEBAR_KEY, next ? '1' : '0')
      return next
    })
  }

  function doLogout() {
    void logout().finally(() => navigate('/', { replace: true }))
  }

  return (
    <div className="dash-shell">
      <aside className={`dash-sidebar${collapsed ? ' is-collapsed' : ''}`}>
        <div className="dash-sidebar-top">
          <NavLink to="/app/overview" className="dash-side-brand" title="IchiVol">
            <span className="dash-side-mark">IV</span>
            <span className="dash-side-name">IchiVol</span>
          </NavLink>

          <nav className="dash-nav" aria-label="Navigation">
            {NAV_ITEMS.map(({ to, label, Icon }) => (
              <NavLink
                key={to}
                to={to}
                title={label}
                className={({ isActive }) => `dash-nav-link${isActive ? ' is-active' : ''}`}
              >
                <Icon />
                <span>{label}</span>
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="dash-sidebar-footer">
          <ThemeToggle />
          <button
            type="button"
            className="dash-collapse-btn"
            aria-label={collapsed ? 'Déplier' : 'Replier'}
            onClick={toggleCollapsed}
          >
            <IconChevronLeft className={collapsed ? 'is-flipped' : undefined} />
          </button>
        </div>
      </aside>

      <div className="dash-main">
        <header className="dash-header">
          <div className="dash-header-right">
            <LlmHeaderBadge />

            <NotificationBell onOpen={() => setUserMenuOpen(false)} />

            <div className="dash-popover-wrap">
              <button
                type="button"
                className="dash-user-btn"
                aria-expanded={userMenuOpen}
                onClick={() => {
                  setUserMenuOpen((v) => !v)
                  // click-outside on bell closes it; ensure menu wins focus
                }}
              >
                <span className="dash-avatar">{email ? email[0].toUpperCase() : '·'}</span>
                <span className="dash-user-label">{email ?? 'admin'}</span>
              </button>
              {userMenuOpen && (
                <div className="dash-popover dash-popover-right">
                  <p className="dash-user-email mono">{email ?? '…'}</p>
                  <p className="dash-user-llm muted">
                    {llmStatusLabel(llm.state)}
                    {llm.provider && llm.model ? ` · ${llm.provider}/${llm.model}` : ''}
                  </p>
                  <Link
                    to="/app/settings"
                    className="ghost dash-popover-action"
                    onClick={() => setUserMenuOpen(false)}
                  >
                    Paramètres
                  </Link>
                  <button type="button" className="ghost dash-popover-action" onClick={doLogout}>
                    Déconnexion
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        <div className="dash-content">
          <Outlet />
        </div>
      </div>

      <AgentChat />
    </div>
  )
}

export function DashboardShell() {
  return (
    <MarketSnapshotProvider>
      <AgentSessionProvider>
        <LlmStatusProvider>
          <DashboardShellInner />
        </LlmStatusProvider>
      </AgentSessionProvider>
    </MarketSnapshotProvider>
  )
}
