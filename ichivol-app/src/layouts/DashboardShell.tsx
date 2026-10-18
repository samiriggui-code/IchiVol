import { useCallback, useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { FicheHost } from '../components/fiches/FicheHost'
import { NotificationBell } from '../components/NotificationBell'
import {
  IconChevronLeft,
  IconClose,
  IconMenu,
} from '../components/NavIcons'
import { BrandMark } from '../components/BrandMark'
import { KillLockBanner, KillSwitchButton, KillSwitchProvider } from '../components/KillSwitchControls'
import { ThemeToggle } from '../components/ThemeToggle'
import { combineOverviews, loadAllBooks } from '../lib/allBooks'
import { getMe, logout } from '../lib/auth'
import { getPaperAutonomy } from '../lib/eveApi'
import type { PaperOverview } from '../lib/paper'
import { AgentSessionProvider } from '../lib/agentSession'
import {
  jevStatusLabel,
  llmStatusLabel,
  LlmStatusProvider,
  useLlmStatus,
} from '../lib/llmStatus'
import { MarketSnapshotProvider } from '../lib/marketSnapshot'
import {
  MOBILE_MORE_ITEMS,
  MOBILE_PRIMARY_ITEMS,
  NAV_GROUPS,
} from '../lib/workspaceNav'

const SIDEBAR_KEY = 'ichivol_sidebar_collapsed'
const MOBILE_MQ = '(max-width: 768px)'

const ACCOUNT_REFRESH_MS = 60_000

type EngineState = 'checking' | 'ok' | 'down'

/**
 * Données du bandeau : uniquement ce que l'app sait déjà charger
 * (vue d'ensemble des portefeuilles paper actifs + état du pilote d'Ève).
 * Rien n'est inventé : une valeur absente s'affiche « — ».
 */
function useShellAccount() {
  const [account, setAccount] = useState<PaperOverview['account'] | null>(null)
  const [engine, setEngine] = useState<EngineState>('checking')
  const [autonomy, setAutonomy] = useState<boolean | null>(null)

  const refresh = useCallback(() => {
    loadAllBooks()
      .then((books) => {
        setEngine('ok')
        setAccount(combineOverviews(books)?.account ?? null)
      })
      .catch(() => {
        setEngine('down')
        setAccount(null)
      })
    getPaperAutonomy()
      .then(setAutonomy)
      .catch(() => setAutonomy(null))
  }, [])

  useEffect(() => {
    refresh()
    const t = window.setInterval(refresh, ACCOUNT_REFRESH_MS)
    return () => window.clearInterval(t)
  }, [refresh])

  return { account, engine, autonomy }
}

const EUR = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

function fmtMoney(v: number | null | undefined, signed = false): string {
  if (v == null || !Number.isFinite(v)) return '—'
  const s = EUR.format(Math.abs(v))
  if (!signed || v === 0) return v < 0 ? `−${s}` : s
  return v > 0 ? `+${s}` : `−${s}`
}

function toneOf(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v) || v === 0) return ''
  return v > 0 ? ' pos' : ' neg'
}

function fmtShare(part: number | null | undefined, total: number | null | undefined): string {
  if (part == null || total == null || !Number.isFinite(part) || !Number.isFinite(total) || total <= 0) {
    return '—'
  }
  return `${new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 1, minimumFractionDigits: 1 }).format((part / total) * 100)} %`
}

function HeaderAccount({ account }: { account: PaperOverview['account'] | null }) {
  const netLiq = account ? (account.liquidation_value ?? account.equity) : null
  return (
    <div className="dash-acct" aria-label="Compte paper, tous les portefeuilles">
      <div className="dash-kv">
        <span className="dash-kv-k">Net liq</span>
        <span className="dash-kv-v">{fmtMoney(netLiq)}</span>
      </div>
      <div className="dash-kv">
        <span className="dash-kv-k">P&amp;L jour</span>
        <span className={`dash-kv-v${toneOf(account?.day_change)}`}>
          {fmtMoney(account?.day_change, true)}
        </span>
      </div>
      <div className="dash-kv">
        <span className="dash-kv-k">P&amp;L latent</span>
        <span className={`dash-kv-v${toneOf(account?.unrealized_pnl)}`}>
          {fmtMoney(account?.unrealized_pnl, true)}
        </span>
      </div>
      <div className="dash-kv">
        <span className="dash-kv-k">Engagé</span>
        <span className="dash-kv-v">{fmtShare(account?.invested, account?.equity)}</span>
      </div>
    </div>
  )
}

function dotTone(state: string): string {
  if (state === 'ok') return ''
  if (state === 'checking' || state === 'idle') return ' is-off'
  if (state === 'disabled') return ' is-off'
  if (state === 'no_key' || state === 'bad_key') return ' is-amber'
  return ' is-sell'
}

function HeaderConnections({ engine }: { engine: EngineState }) {
  const { state, jevos, typesafe, refresh } = useLlmStatus()
  const chatLabel = llmStatusLabel(state)
  const engineLabel =
    engine === 'ok' ? 'Moteur joignable' : engine === 'down' ? 'Moteur injoignable' : 'Moteur…'
  // Libellés produit uniquement : pas de marque, fournisseur, modèle ni URL.
  const detail = [engineLabel, `JEV ${jevStatusLabel(jevos)}`, `JEV ${jevStatusLabel(typesafe)}`, chatLabel].join(' · ')

  return (
    <button
      type="button"
      className="dash-conn llm-status-badge"
      title={`${detail} (cliquer pour retester)`}
      aria-label={detail}
      onClick={() => void refresh()}
    >
      <span className={`dash-conn-item is-${engine}`} title={engineLabel}>
        <i className={`iv-dot${dotTone(engine)}`} aria-hidden />
        <span className="dash-conn-text">Moteur</span>
      </span>
      <span className={`dash-conn-item is-${jevos.state}`} title={`JEV ${jevStatusLabel(jevos)}`}>
        <i className={`iv-dot${dotTone(jevos.state)}`} aria-hidden />
        <span className="dash-conn-text">JEV local</span>
      </span>
      <span className={`dash-conn-item is-${typesafe.state}`} title={`JEV ${jevStatusLabel(typesafe)}`}>
        <i className={`iv-dot${dotTone(typesafe.state)}`} aria-hidden />
        <span className="dash-conn-text">JEV cloud</span>
      </span>
      <span className={`dash-conn-item is-${state}`} title={chatLabel}>
        <i className={`iv-dot${dotTone(state)}`} aria-hidden />
        <span className="dash-conn-text">Copilot</span>
      </span>
    </button>
  )
}

function PilotPill({ autonomy }: { autonomy: boolean | null }) {
  if (autonomy === true) {
    return (
      <span className="iv-pill is-mint dash-pilot" title="Ève accepte ou refuse ce que le moteur propose">
        Pilote Ève
      </span>
    )
  }
  return (
    <span
      className="iv-pill is-muted dash-pilot"
      title={autonomy === false ? 'Pilote automatique d’Ève désactivé' : 'État du pilote d’Ève inconnu'}
    >
      Pilote Ève · {autonomy === false ? 'off' : '—'}
    </span>
  )
}

function DashboardShellInner() {
  const navigate = useNavigate()
  const location = useLocation()
  const llm = useLlmStatus()
  const shell = useShellAccount()
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
          <NavLink to="/app/desk" className="dash-side-brand" title="IchiVol">
            <BrandMark className="dash-side-mark" />
            <span className="dash-side-name">
              IchiVol
              <small>Poste paper</small>
            </span>
          </NavLink>

          <nav className="dash-nav">
            {NAV_GROUPS.map((group) => (
              <div key={group.id} className="dash-nav-group">
                <p className="dash-nav-label">{group.label}</p>
                {group.items.map(({ to, label, Icon }) => (
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
              </div>
            ))}
          </nav>
        </div>

        <div className="dash-sidebar-footer">
          <span
            className="dash-side-status"
            title={
              shell.engine === 'ok'
                ? 'Moteur joignable'
                : shell.engine === 'down'
                  ? 'Moteur injoignable'
                  : 'Moteur…'
            }
          >
            <i className={`iv-dot${dotTone(shell.engine)}`} aria-hidden />
            <span>Moteur</span>
          </span>
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
              <NavLink to="/app/desk" className="dash-mobile-brand" title="IchiVol">
                <BrandMark className="dash-side-mark" />
                <span>IchiVol</span>
              </NavLink>
            )}
            <HeaderAccount account={shell.account} />
            <HeaderConnections engine={shell.engine} />
          </div>
          <div className="dash-header-right">
            <PilotPill autonomy={shell.autonomy} />
            <span
              className="iv-pill dash-paper-pill"
              data-mode="paper"
              title="Paper trading : aucune exécution réelle"
            >
              PAPER
            </span>
            <KillSwitchButton />

            <NotificationBell onOpen={() => setUserMenuOpen(false)} />

            <div className="dash-popover-wrap dash-user-wrap">
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
                    {' · '}
                    {jevStatusLabel(llm.jevos)}
                    {' · '}
                    {jevStatusLabel(llm.typesafe)}
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
        <FicheHost />
      </div>

      {isMobile && (
        <>
          <nav className="dash-mobile-tabbar" aria-label="Navigation principale">
            {MOBILE_PRIMARY_ITEMS.map(({ to, label, Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) => `dash-mobile-tab${isActive ? ' is-active' : ''}`}
                onClick={(e) => {
                  /* Re-tap onglet actif → ferme fiche (?symbol=) / query et revient à la liste */
                  if (location.pathname === to && location.search) {
                    e.preventDefault()
                    navigate(to)
                  }
                }}
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
            <div className="dash-mobile-more-head">
              <p className="dash-mobile-more-title">Plus</p>
              <ThemeToggle />
            </div>
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
            <div className="dash-mobile-more-foot">
              <span className="mono">{email ?? '…'}</span>
              <button type="button" className="iv-btn iv-btn--sm iv-btn--ghost" onClick={doLogout}>
                Déconnexion
              </button>
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
