import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { NotificationBell } from '../components/NotificationBell'
import {
  IconChevronLeft,
  IconClose,
  IconMenu,
} from '../components/NavIcons'
import { BrandMark } from '../components/BrandMark'
import { KillLockBanner, KillSwitchButton, KillSwitchProvider } from '../components/KillSwitchControls'
import { ThemeToggle } from '../components/ThemeToggle'
import { getMe, logout } from '../lib/auth'
import { AgentSessionProvider } from '../lib/agentSession'
import { llmStatusLabel, LlmStatusProvider, useLlmStatus } from '../lib/llmStatus'
import { MarketSnapshotProvider } from '../lib/marketSnapshot'
import {
  MOBILE_MORE_ITEMS,
  MOBILE_PRIMARY_ITEMS,
  NAV_GROUPS,
} from '../lib/workspaceNav'

const SIDEBAR_KEY = 'ichivol_sidebar_collapsed'
const MOBILE_MQ = '(max-width: 768px)'

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
          <NavLink to="/app/desk" className="dash-side-brand brand" title="IchiVol">
            <span className="brandmark dash-side-mark" aria-hidden>
              ∿
            </span>
            <span className="dash-side-name">
              IchiVol<small>V3</small>
            </span>
          </NavLink>

          <nav className="dash-nav">
            {NAV_GROUPS.filter((g) => g.id !== 'system').map((group) => (
              <div key={group.id} className="dash-nav-group">
                <div className="nav-label dash-nav-label">{group.label}</div>
                {group.items.map(({ to, label, glyph }) => (
                  <NavLink
                    key={to}
                    to={to}
                    title={label}
                    className={({ isActive }) => `dash-nav-link${isActive ? ' is-active active' : ''}`}
                  >
                    <span className="icon" aria-hidden>
                      {glyph ?? '·'}
                    </span>
                    {label}
                    {to === '/app/opportunites' ? <em>07</em> : null}
                  </NavLink>
                ))}
              </div>
            ))}
          </nav>
        </div>

        <div className="dash-sidebar-footer side-bottom">
          <NavLink
            to="/app/settings"
            className={({ isActive }) => `settings-link${isActive ? ' active' : ''}`}
          >
            <span aria-hidden>⚙</span> Paramètres
          </NavLink>
          <strong>Votre espace paper</strong>
          Ichimoku × RVOL
          <span style={{ font: "9px 'DM Mono'", display: 'block', marginTop: 15 }}>
            V3.0 / INTERFACE PREVIEW
          </span>
          {!isMobile && (
            <button
              type="button"
              className="dash-collapse-btn"
              aria-label={collapsed ? 'Déplier' : 'Replier'}
              onClick={toggleCollapsed}
              style={{ marginTop: 12 }}
            >
              <IconChevronLeft className={collapsed ? 'is-flipped' : undefined} />
            </button>
          )}
        </div>
      </aside>

      <div className="dash-main">
        <header className="dash-header">
          <div className="dash-header-left">
            {isMobile && (
              <NavLink to="/app/desk" className="dash-mobile-brand" title="IchiVol">
                <BrandMark className="dash-side-mark" />
                <span>IchiVol</span>
              </NavLink>
            )}
          </div>
          <div className="dash-header-right header-right">
            <span className="engine">◌ Moteur non connecté</span>
            <span className="pill">PAPER · DÉMO</span>
            <KillSwitchButton />
            <Link to="/app/settings" className="header-settings" aria-label="Ouvrir les paramètres" title="Paramètres">
              ⚙
            </Link>
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
                <span className="avatar dash-avatar">{email ? email[0].toUpperCase() : 'SI'}</span>
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

        <KillLockBanner />
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
    </div>
  )
}

export function DashboardShell() {
  return (
    <MarketSnapshotProvider>
      <AgentSessionProvider>
        <LlmStatusProvider>
          <KillSwitchProvider>
            <DashboardShellInner />
          </KillSwitchProvider>
        </LlmStatusProvider>
      </AgentSessionProvider>
    </MarketSnapshotProvider>
  )
}
