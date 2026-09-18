import { useEffect, useState, type ComponentType } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { AgentChat } from '../components/AgentChat'
import { NotificationBell } from '../components/NotificationBell'
import {
  IconBacktests,
  IconChat,
  IconChevronLeft,
  IconClose,
  IconDecisions,
  IconGlobe,
  IconJournal,
  IconMarket,
  IconMenu,
  IconOverview,
  IconPaper,
  IconSettings,
  IconWatchlist,
} from '../components/NavIcons'
import { BrandMark } from '../components/BrandMark'
import { ThemeToggle } from '../components/ThemeToggle'
import { getMe, logout } from '../lib/auth'
import { AgentSessionProvider } from '../lib/agentSession'
import { llmStatusLabel, LlmStatusProvider, useLlmStatus } from '../lib/llmStatus'
import { MarketSnapshotProvider } from '../lib/marketSnapshot'

const SIDEBAR_KEY = 'ichivol_sidebar_collapsed'
const MOBILE_MQ = '(max-width: 768px)'

type NavItem = {
  to: string
  label: string
  Icon: ComponentType<{ className?: string }>
}

const NAV_ITEMS: NavItem[] = [
  { to: '/app/overview', label: 'Overview', Icon: IconOverview },
  { to: '/app/market', label: 'Marché', Icon: IconMarket },
  { to: '/app/context', label: 'Contexte', Icon: IconGlobe },
  { to: '/app/decisions', label: 'Décisions', Icon: IconDecisions },
  { to: '/app/journal', label: 'Journal', Icon: IconJournal },
  { to: '/app/watchlist', label: 'Watchlist', Icon: IconWatchlist },
  { to: '/app/paper', label: 'Paper', Icon: IconPaper },
  { to: '/app/backtests', label: 'Backtests', Icon: IconBacktests },
  { to: '/app/agent', label: 'Copilot', Icon: IconChat },
  { to: '/app/settings', label: 'Settings', Icon: IconSettings },
]

/** Primary tabs on phone — rest go in the « Plus » sheet. */
const MOBILE_PRIMARY = new Set([
  '/app/overview',
  '/app/market',
  '/app/decisions',
  '/app/agent',
])

const MOBILE_PRIMARY_ITEMS = NAV_ITEMS.filter((item) => MOBILE_PRIMARY.has(item.to))
const MOBILE_MORE_ITEMS = NAV_ITEMS.filter((item) => !MOBILE_PRIMARY.has(item.to))

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
  const location = useLocation()
  const llm = useLlmStatus()
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(SIDEBAR_KEY) === '1')
  const [isMobile, setIsMobile] = useState(() =>
    typeof window !== 'undefined' ? window.matchMedia(MOBILE_MQ).matches : false,
  )
  const [email, setEmail] = useState<string | null>(null)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [moreOpen, setMoreOpen] = useState(false)

  const moreActive = MOBILE_MORE_ITEMS.some(
    (item) => location.pathname === item.to || location.pathname.startsWith(`${item.to}/`),
  )

  useEffect(() => {
    getMe().then((user) => setEmail(user?.email ?? null))
  }, [])

  useEffect(() => {
    const mq = window.matchMedia(MOBILE_MQ)
    const apply = () => {
      const mobile = mq.matches
      setIsMobile(mobile)
      if (mobile) {
        setCollapsed(true)
      } else {
        setMoreOpen(false)
      }
    }
    apply()
    mq.addEventListener('change', apply)
    return () => mq.removeEventListener('change', apply)
  }, [])

  useEffect(() => {
    setMoreOpen(false)
    setUserMenuOpen(false)
  }, [location.pathname])

  useEffect(() => {
    if (!moreOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMoreOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [moreOpen])

  function toggleCollapsed() {
    if (isMobile) return
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
    <div className={`dash-shell${isMobile ? ' is-mobile' : ''}${collapsed ? ' is-nav-collapsed' : ''}`}>
      <aside className={`dash-sidebar${collapsed ? ' is-collapsed' : ''}`} aria-label="Navigation">
        <div className="dash-sidebar-top">
          <NavLink to="/app/overview" className="dash-side-brand" title="IchiVol">
            <BrandMark className="dash-side-mark" />
            <span className="dash-side-name">IchiVol</span>
          </NavLink>

          <nav className="dash-nav">
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
          <div className="dash-header-left">
            {isMobile && (
              <NavLink to="/app/overview" className="dash-mobile-brand" title="IchiVol">
                <BrandMark className="dash-side-mark" />
                <span>IchiVol</span>
              </NavLink>
            )}
          </div>
          <div className="dash-header-right">
            {isMobile && <ThemeToggle />}
            <LlmHeaderBadge />

            <NotificationBell onOpen={() => setUserMenuOpen(false)} />

            <div className="dash-popover-wrap">
              <button
                type="button"
                className="dash-user-btn"
                aria-expanded={userMenuOpen}
                onClick={() => {
                  setUserMenuOpen((v) => !v)
                  setMoreOpen(false)
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

      {isMobile && (
        <>
          <nav className="dash-mobile-tabbar" aria-label="Navigation principale">
            {MOBILE_PRIMARY_ITEMS.map(({ to, label, Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) => `dash-mobile-tab${isActive ? ' is-active' : ''}`}
              >
                <Icon />
                <span>{label}</span>
              </NavLink>
            ))}
            <button
              type="button"
              className={`dash-mobile-tab${moreActive || moreOpen ? ' is-active' : ''}`}
              aria-expanded={moreOpen}
              aria-controls="dash-mobile-more"
              onClick={() => {
                setMoreOpen((v) => !v)
                setUserMenuOpen(false)
              }}
            >
              {moreOpen ? <IconClose /> : <IconMenu />}
              <span>Plus</span>
            </button>
          </nav>

          {moreOpen && (
            <div
              className="dash-mobile-more-backdrop"
              onClick={() => setMoreOpen(false)}
              aria-hidden
            />
          )}
          <div
            id="dash-mobile-more"
            className={`dash-mobile-more${moreOpen ? ' is-open' : ''}`}
            role="dialog"
            aria-modal="true"
            aria-label="Autres pages"
            hidden={!moreOpen}
          >
            <div className="dash-mobile-more-handle" aria-hidden />
            <p className="dash-mobile-more-title">Plus</p>
            <div className="dash-mobile-more-grid">
              {MOBILE_MORE_ITEMS.map(({ to, label, Icon }) => (
                <NavLink
                  key={to}
                  to={to}
                  className={({ isActive }) => `dash-mobile-more-link${isActive ? ' is-active' : ''}`}
                  onClick={() => setMoreOpen(false)}
                >
                  <Icon />
                  <span>{label}</span>
                </NavLink>
              ))}
            </div>
          </div>
        </>
      )}

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
