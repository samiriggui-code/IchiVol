/**
 * Desk : le portefeuille paper unique, le marché et Ève, sur les primitives premium (iv-).
 * Mise en page = maquette « poste de trading » validée. Données = moteur (rien d'inventé ; manquant → « — »).
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  getActivityFeed,
  type ActivityItem,
  type FeedTone,
} from '../lib/activity'
import {
  getScreener,
  type ScreenerDecisionRow,
} from '../lib/decisions'
import { fetchTickers24h } from '../lib/binance'
import {
  fetchFearGreed,
  fetchGlobalMarket,
  type FearGreed,
  type GlobalMarketData,
} from '../lib/marketContext'
import {
  MARKET_SESSIONS,
  formatCountdown,
  formatSessionHoursUtc,
  formatVenueClock,
  nextHourlyClose,
  nextSessionOpen,
  sessionStatus,
  sessionStatusLabel,
  wallTimeToUtc,
  type MarketSessionDef,
  type SessionId,
  type SessionStatus,
} from '../lib/marketSessions'
import {
  getPaperActivity,
  getPaperOverview,
  loadAccountLots,
  type PaperOrderRow,
  type PaperOverview,
  type PaperOverviewPosition,
} from '../lib/paper'
import { getRiskLock, type RiskLockState } from '../lib/riskLock'
import { MAIN_PORTFOLIO_CODE, MAIN_PORTFOLIO_LABEL } from '../lib/mainPortfolio'
import { getPortfolioBreakdown, type PortfolioBreakdown } from '../lib/breakdown'
import { verdictBucket } from '../lib/deskSummarize'
import { concentrationFromPositions } from '../components/desk/deskMetrics'
import {
  PRIMARY_SYMBOLS,
  REFRESH_MS,
  fmtClock,
  fmtDec,
  fmtEur,
  fmtPct,
  fmtPctPoints,
  fmtPrice,
  type EquityPeriod,
} from './desk/deskFormat'
import { toEngineSymbol } from '../lib/engineSymbol'
import { EquityTrajectory, type TrajectoryBook } from '../components/desk/EquityTrajectory'
import { MAIN_CURVE_COLOR, cleanEquitySeries } from '../components/desk/equityTrajectory'
import { DeskDeciderSummary, DeskEveLatest } from '../components/decider/DeskDeciders'
import { DeciderBadge } from '../components/decider/DeciderBadge'
import { deciderOf, type Decider } from '../lib/decider'
import { usePaged } from '../components/table/usePaged'
import { TablePager } from '../components/table/TablePager'
import './OverviewPage.css'

const RVOL_THRESHOLD = 1.5
const EQUITY_PERIODS: EquityPeriod[] = ['1J', '1S', '1M', '3M']
/** Places montrées dans la carte des sessions (la crypto ne ferme jamais). */
const DESK_SESSIONS: SessionId[] = ['sydney', 'tokyo', 'london', 'newyork', 'chicago', 'crypto']

type Tone = 'mint' | 'amber' | 'sell' | 'cyan' | 'buy' | 'muted' | ''

function Tag({ children, tone = '' }: { children: ReactNode; tone?: Tone }) {
  return <span className={`iv-tag${tone ? ` is-${tone}` : ''}`}>{children}</span>
}

function statusTone(text: string): Tone {
  if (/PASSE|ACCEPTÉ|OUVERTE|VALIDÉ|CONNECTÉ|ÉQUILIBRÉ/.test(text)) return 'mint'
  if (/REFUS|BLOQU|ERREUR|HORS/.test(text)) return 'sell'
  if (/PRUDENCE|TRIGGERED|RETARD|STALE/.test(text)) return 'amber'
  return 'muted'
}

/** Carte station : onglets (ou un titre), outils à droite, corps, pied. */
function Card({
  title,
  tabs,
  tools,
  foot,
  flush = false,
  glow = false,
  className = '',
  bodyClassName = '',
  children,
}: {
  title?: string
  tabs?: ReactNode
  tools?: ReactNode
  foot?: ReactNode
  flush?: boolean
  glow?: boolean
  className?: string
  bodyClassName?: string
  children: ReactNode
}) {
  return (
    <section className={`iv-card${glow ? ' iv-glow' : ''} ${className}`.trim()}>
      <div className="iv-card-head">
        <div className="iv-card-tabs" role={tabs ? 'tablist' : undefined}>
          {tabs ?? <h2 className="iv-card-tab is-on dk-title">{title}</h2>}
        </div>
        {tools ? <div className="iv-card-tools">{tools}</div> : null}
      </div>
      <div className={`iv-card-body${flush ? ' is-flush' : ''} ${bodyClassName}`.trim()}>{children}</div>
      {foot ? <div className="iv-card-foot">{foot}</div> : null}
    </section>
  )
}

function TabButton({ on, onClick, children }: { on: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={on}
      className={`iv-card-tab${on ? ' is-on' : ''}`}
      onClick={onClick}
    >
      {children}
    </button>
  )
}

function Row({ label, value, className = '' }: { label: ReactNode; value: ReactNode; className?: string }) {
  return (
    <div className="iv-row">
      <span>{label}</span>
      <span className={`iv-row-v ${className}`.trim()}>{value}</span>
    </div>
  )
}

function Meter({
  label,
  value,
  pct,
  tone = '',
}: {
  label: string
  value: string
  pct: number | null
  tone?: '' | 'amber' | 'mint'
}) {
  const width = pct == null ? 0 : Math.max(0, Math.min(100, pct))
  return (
    <div className="dk-meter">
      <div className="dk-meter-top">
        <span>{label}</span>
        <span className={`mono${tone === 'amber' ? ' warn' : ''}`}>{value}</span>
      </div>
      <div className={`iv-bar${tone ? ` is-${tone}` : ''}`}>
        <i style={{ width: `${width}%` }} />
      </div>
    </div>
  )
}

/** « 81 136,85 € » → partie entière en grand, décimales en petit (comme la maquette). */
function SplitEur({ value }: { value: number | null | undefined }) {
  if (value == null || !Number.isFinite(value)) return <>—</>
  const s = fmtEur(value, 2)
  const i = s.lastIndexOf(',')
  if (i < 0) return <>{s}</>
  return (
    <>
      {s.slice(0, i)}
      <small>{s.slice(i)}</small>
    </>
  )
}

function signedEur(v: number | null | undefined, digits = 2): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return `${v > 0 ? '+' : v < 0 ? '−' : ''}${fmtEur(Math.abs(v), digits)}`
}

function signCls(v: number | null | undefined): string {
  return v == null || !Number.isFinite(v) || v === 0 ? '' : v > 0 ? 'pos' : 'neg'
}

function fmtQty(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return Math.abs(v).toLocaleString('fr-FR', { maximumFractionDigits: Math.abs(v) >= 100 ? 0 : 4 })
}

/** Courbe miniature d'un bandeau de KPI (vraies valeurs de la courbe de capital). */
function Spark({ values }: { values: number[] }) {
  if (values.length < 2) return null
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const pts = values
    .map((v, i) => `${((i / (values.length - 1)) * 60).toFixed(1)},${(20 - ((v - min) / span) * 18 - 1).toFixed(1)}`)
    .join(' ')
  return (
    <svg className="dk-spark" viewBox="0 0 60 20" preserveAspectRatio="none" aria-hidden="true">
      <polyline points={pts} />
    </svg>
  )
}

function pickPrimaryMarkets(rows: ScreenerDecisionRow[]): ScreenerDecisionRow[] {
  const bySym = new Map(rows.map((r) => [r.symbol.toUpperCase(), r]))
  const preferred = PRIMARY_SYMBOLS.map((s) => bySym.get(s)).filter(
    (r): r is ScreenerDecisionRow => Boolean(r),
  )
  if (preferred.length >= 4) return preferred.slice(0, 4)
  const rest = [...rows]
    .filter((r) => !PRIMARY_SYMBOLS.includes(r.symbol.toUpperCase()))
    .sort((a, b) => b.confidence - a.confidence)
  return [...preferred, ...rest].slice(0, 4)
}

function drawdownRatio(
  curve: { equity: number; t?: string }[],
  equity: number | null | undefined,
): number | null {
  const band = cleanEquitySeries(
    curve.map((p, i) => ({ t: p.t ?? `i${i}`, equity: p.equity })),
  ).map((p) => p.equity)
  if (equity == null || !Number.isFinite(equity) || band.length === 0) return null
  let peak = equity
  for (const v of band) {
    if (v > peak) peak = v
  }
  if (peak <= 0) return null
  return (equity - peak) / peak
}

function fearGreedFr(classification: string): string {
  switch (classification.toLowerCase()) {
    case 'extreme fear':
      return 'Peur extrême'
    case 'fear':
      return 'Peur'
    case 'neutral':
      return 'Neutre'
    case 'greed':
      return 'Avidité'
    case 'extreme greed':
      return 'Avidité extrême'
    default:
      return classification
  }
}

function decisionFr(label: string): string {
  switch (label) {
    case 'STRONG_BUY':
      return 'Achat fort'
    case 'BUY':
      return 'Achat'
    case 'WATCH':
      return 'Veille'
    case 'WAIT':
      return 'Attente'
    case 'SELL':
      return 'Vente'
    case 'STRONG_SELL':
      return 'Vente forte'
    case 'NO_TRADE':
      return 'Sans trade'
    default:
      return label
  }
}

function sessionTone(st: SessionStatus): Tone {
  switch (st) {
    case 'open':
      return 'mint'
    case 'upcoming':
      return 'amber'
    case 'closed':
      return 'muted'
    default: {
      const _e: never = st
      return _e
    }
  }
}

function opportunityCaption(r: ScreenerDecisionRow): string {
  const stages = r.pipeline?.stages
  if (stages?.length) {
    const failed = stages.find((s) => s.status === 'fail')
    if (failed?.summary) return failed.summary
    const pending = stages.find((s) => s.status === 'pending' || s.status === 'watch')
    if (pending?.summary) return pending.summary
    const allOk = stages.every((s) => s.status === 'pass' || s.status === 'skip')
    if (allOk) return 'Toutes les portes sont passées'
  }
  if (r.decision) return String(r.decision)
  return '—'
}

function decisionTone(r: ScreenerDecisionRow): Tone {
  const b = verdictBucket(r)
  return b === 'buy' ? 'buy' : b === 'sell' ? 'sell' : b === 'watch' ? 'amber' : 'muted'
}

/** Répartition de l'exposition ouverte entre crypto (paires USDT) et le reste (indices, forex, matières premières). */
function exposureMixLabel(positions: Array<{ symbol: string; notional?: number | null; market_value?: number | null }>): string {
  let crypto = 0
  let other = 0
  for (const p of positions) {
    const v = Math.abs(p.market_value ?? p.notional ?? 0)
    if (!Number.isFinite(v) || v <= 0) continue
    if (/USDT$/i.test(p.symbol)) crypto += v
    else other += v
  }
  const total = crypto + other
  if (total <= 0) return 'Aucune exposition ouverte.'
  const pc = Math.round((crypto / total) * 100)
  if (pc === 100) return '100 % de l’exposition en crypto.'
  if (pc === 0) return '100 % de l’exposition hors crypto (indices, forex, matières premières).'
  return `${pc} % de l’exposition en crypto, ${100 - pc} % hors crypto (indices, forex, matières premières).`
}

const FEED_LEVEL: Record<FeedTone, { label: string; tone: Tone }> = {
  neutral: { label: 'INFO', tone: 'cyan' },
  good: { label: 'OK', tone: 'mint' },
  bad: { label: 'ALERTE', tone: 'amber' },
  blocked: { label: 'BLOQUÉ', tone: 'sell' },
}

/** Heure UTC décimale (0–24) d'une heure locale de place, pour la frise des sessions. */
function utcHourOf(def: MarketSessionDef, localHour: number, now: Date): number {
  const h = Math.floor(localHour)
  const m = Math.round((localHour - h) * 60)
  const d = wallTimeToUtc(now.getUTCFullYear(), now.getUTCMonth() + 1, now.getUTCDate(), h, m, def.timeZone)
  return d.getUTCHours() + d.getUTCMinutes() / 60
}

/** Segments [début, fin] en % de la journée UTC où la place est ouverte. */
function sessionSegments(def: MarketSessionDef, now: Date): Array<[number, number]> {
  if (def.kind === 'always') return [[0, 100]]
  // CME : ouvert tout le jour sauf la pause de 16 h à 17 h (heure de Chicago).
  const [openL, closeL] = def.kind === 'futures_cme' ? [17, 16] : [def.openLocal, def.closeLocal]
  const a = utcHourOf(def, openL, now)
  const b = utcHourOf(def, closeL, now)
  const pa = (a / 24) * 100
  const pb = (b / 24) * 100
  return pb > pa ? [[pa, pb]] : [[pa, 100], [0, pb]]
}

const ORDER_STATUS_FR: Record<string, string> = {
  FILLED: 'Exécuté',
  PARTIALLY_FILLED: 'Partiel',
  REJECTED: 'Rejeté',
  CANCELLED: 'Annulé',
}

type PositionsTab = 'positions' | 'orders' | 'concentration'

export function OverviewPage() {
  const navigate = useNavigate()
  const [rows, setRows] = useState<ScreenerDecisionRow[]>([])
  const [loading, setLoading] = useState(true)
  const [overview, setOverview] = useState<PaperOverview | null>(null)
  const [tape, setTape] = useState<ActivityItem[]>([])
  const [paperOrders, setPaperOrders] = useState<PaperOrderRow[]>([])
  const [lock, setLock] = useState<RiskLockState | null>(null)
  const [engineOk, setEngineOk] = useState<boolean | null>(null)
  const [market, setMarket] = useState<GlobalMarketData | null>(null)
  const [fng, setFng] = useState<FearGreed | null>(null)
  const [changeBySymbol, setChangeBySymbol] = useState<Record<string, number>>({})
  const [sessionId, setSessionId] = useState<SessionId>('crypto')
  const [equityPeriod, setEquityPeriod] = useState<EquityPeriod>('1M')
  const [nowTick, setNowTick] = useState(() => Date.now())
  const [deciderByPosition, setDeciderByPosition] = useState<Record<string, Decider>>({})
  const [breakdown, setBreakdown] = useState<PortfolioBreakdown | null>(null)

  const load = useCallback(async (force = false) => {
    setLoading(true)
    type ScreenerOk = Awaited<ReturnType<typeof getScreener>>
    void loadAccountLots()
      .then((lots) => setDeciderByPosition(Object.fromEntries(lots.map((p) => [p.id, deciderOf(p)]))))
      .catch(() => undefined)
    // Desk = le portefeuille paper unique (ICHIVOL_MAIN_V1) : totaux, positions, ordres, verrou.
    void getPortfolioBreakdown(MAIN_PORTFOLIO_CODE)
      .then(setBreakdown)
      .catch(() => setBreakdown(null))
    const [screenerRes, ovRes, feedRes, ordersRes, lockRes, healthRes, mktRes, fngRes, tickersRes] =
      await Promise.all([
        getScreener('1h', force)
          .then((r): ScreenerOk | Error => r)
          .catch((err: unknown): ScreenerOk | Error =>
            err instanceof Error ? err : new Error('Screener indisponible'),
          ),
        getPaperOverview(MAIN_PORTFOLIO_CODE)
          .then((data) => ({ ok: true as const, data }))
          .catch(() => ({ ok: false as const })),
        getActivityFeed(100)
          .then((r) => ({ ok: true as const, items: r.items }))
          .catch(() => ({ ok: false as const, items: [] as ActivityItem[] })),
        getPaperActivity(MAIN_PORTFOLIO_CODE, 200)
          .then((orders) => ({ ok: true as const, orders }))
          .catch(() => ({ ok: false as const, orders: [] as PaperOrderRow[] })),
        getRiskLock(MAIN_PORTFOLIO_CODE).catch(() => null),
        fetch('/api/engine/health', { credentials: 'include' })
          .then(async (res) => {
            if (!res.ok) return { engine: false }
            const j = (await res.json().catch(() => null)) as {
              status?: string
              ok?: boolean
            } | null
            const ok = j?.ok === true || j?.status === 'ok' || j?.status === 'healthy'
            return { engine: Boolean(ok) }
          })
          .catch(() => ({ engine: false })),
        fetchGlobalMarket()
          .then((m) => ({ ok: true as const, data: m }))
          .catch(() => ({ ok: false as const })),
        fetchFearGreed()
          .then((f) => ({ ok: true as const, data: f }))
          .catch(() => ({ ok: false as const })),
        fetchTickers24h()
          .then((list) => {
            const map: Record<string, number> = {}
            for (const t of list) map[t.symbol.toUpperCase()] = t.priceChangePercent
            return map
          })
          .catch(() => ({} as Record<string, number>)),
      ])

    if (screenerRes instanceof Error) {
      setRows([])
    } else {
      setRows(screenerRes.rows)
    }

    if (ovRes.ok) setOverview(ovRes.data)
    else setOverview(null)

    if (feedRes.ok) {
      setTape(feedRes.items)
    } else {
      setTape([])
    }

    if (ordersRes.ok) setPaperOrders(ordersRes.orders)
    else setPaperOrders([])

    setLock(lockRes)
    setEngineOk(healthRes.engine)

    if (mktRes.ok) setMarket(mktRes.data)
    else setMarket(null)
    if (fngRes.ok) setFng(fngRes.data)
    else setFng(null)

    setChangeBySymbol(tickersRes)
    setLoading(false)
  }, [])

  useEffect(() => {
    void load()
    const id = window.setInterval(() => void load(), REFRESH_MS)
    const tick = window.setInterval(() => setNowTick(Date.now()), 15_000)
    return () => {
      window.clearInterval(id)
      window.clearInterval(tick)
    }
  }, [load])

  const now = useMemo(() => new Date(nowTick), [nowTick])
  const acct = overview?.account
  const risk = overview?.risk
  /** Totaux Desk = ceux du portefeuille unique, tels que le moteur les calcule. */
  const deskEquity = acct?.equity
  const deskCash = acct?.cash
  const deskDay = acct?.day_change
  const deskRiskPct = risk?.open_risk_pct
  const deskRiskMax = risk?.max_open_risk_pct
  const dayUp = (deskDay ?? 0) > 0
  const dayPct =
    deskDay != null && deskEquity
      ? deskDay / Math.max(1e-9, deskEquity - deskDay)
      : null

  const watchList = useMemo(() => {
    return rows
      .filter((r) => {
        const b = verdictBucket(r)
        return b === 'buy' || b === 'sell'
      })
      .sort((a, b) => b.confidence - a.confidence)
      .slice(0, 5)
  }, [rows])

  const primaryMarkets = useMemo(() => pickPrimaryMarkets(rows), [rows])

  const freshnessNotice = useMemo(() => {
    const stalePositions = (overview?.positions ?? []).filter((p) => p.mark_stale)
    if (stalePositions.length > 0) {
      const oldest = [...stalePositions].sort(
        (a, b) => (b.mark_age_s ?? 0) - (a.mark_age_s ?? 0),
      )[0]!
      const hours =
        oldest.mark_age_s != null && oldest.mark_age_s > 0
          ? Math.max(1, Math.round(oldest.mark_age_s / 3600))
          : null
      const name = oldest.symbol.replace(/USDT$/i, '')
      return {
        text: hours
          ? `Le cours de ${name} n’a pas été mis à jour depuis ${hours} h.`
          : `Le cours de ${name} est périmé.`,
        href: `/app/portefeuille?symbol=${encodeURIComponent(oldest.symbol)}`,
      }
    }
    const staleRows = rows.filter((r) => r.data_quality?.stale || r.data_quality?.data_late)
    const first = staleRows.find((r) => /^[A-Z0-9]{3,}$/i.test(r.symbol))
    if (!first) return null
    return {
      text: `La lecture de ${first.symbol.replace(/USDT$/i, '')} repose sur une bougie trop ancienne.`,
      href: `/app/opportunites?symbol=${encodeURIComponent(first.symbol)}`,
    }
  }, [rows, overview?.positions])

  const btcRow = rows.find((r) => r.symbol.toUpperCase() === 'BTCUSDT')
  const nextClose = nextHourlyClose(now)
  const selectedSession =
    MARKET_SESSIONS.find((s) => s.id === sessionId) ?? MARKET_SESSIONS[1]
  const selectedSt = sessionStatus(selectedSession, now)

  const investedPct =
    acct && acct.equity > 0 ? Math.min(100, Math.max(0, (acct.invested / acct.equity) * 100)) : null

  const concentration = useMemo(
    () => concentrationFromPositions(overview?.positions ?? []),
    [overview?.positions],
  )

  const dd = drawdownRatio(overview?.equity_curve ?? [], acct?.equity)
  const dateLabel = now.toLocaleDateString('fr-FR', {
    day: 'numeric',
    month: 'long',
  })

  const btcDom = market?.dominance.find((d) => d.symbol.toUpperCase() === 'BTC')
  const topConc = concentration[0]?.pct ?? null
  const concentrationLabel =
    topConc == null ? '—' : topConc >= 40 ? 'PRUDENCE' : 'ÉQUILIBRÉ'

  const climateSymbol =
    fng == null ? '—' : fng.value >= 55 ? '↗' : fng.value <= 45 ? '↘' : '→'
  const btcRegime = btcRow?.pipeline?.stages.find((s) => s.id === 'regime')
  const openSessions = MARKET_SESSIONS.filter((s) => sessionStatus(s, now) === 'open').length
  const nextOpen = nextSessionOpen(selectedSession, now)
  const marketsStale = rows.some((r) => r.data_quality?.stale || r.data_quality?.data_late)

  const riskPass =
    lock == null
      ? null
      : !lock.entries_blocked && !lock.daily_loss_locked && !lock.kill_switch_armed

  const dailyRiskPct =
    risk?.open_risk_pct != null && risk.max_open_risk_pct
      ? (risk.open_risk_pct / risk.max_open_risk_pct) * 100
      : null
  const slotsPct =
    risk && risk.max_open_positions > 0
      ? (risk.open_positions / risk.max_open_positions) * 100
      : null

  const openMarket = (symbol: string) => {
    const full = toEngineSymbol(symbol)
    navigate(`/app/market?symbol=${encodeURIComponent(full)}`)
  }

  const openOpp = (symbol: string) => {
    const full = toEngineSymbol(symbol)
    navigate(`/app/opportunites?symbol=${encodeURIComponent(full)}`)
  }

  const openPosition = (symbol: string) => {
    navigate(`/app/portefeuille?tab=positions&symbol=${encodeURIComponent(symbol)}`)
  }

  const [posTab, setPosTab] = useState<PositionsTab>('positions')

  const invested = acct?.invested ?? null
  const unrealized = acct?.unrealized_pnl ?? null
  const perfPct =
    acct && acct.initial_cash > 0 ? acct.total_pnl / acct.initial_cash : null
  const positions = (overview?.positions ?? []) as PaperOverviewPosition[]
  const shortCount = positions.filter((p) => String(p.direction).toUpperCase() === 'SHORT').length
  const equitySpark = useMemo(
    () =>
      cleanEquitySeries(overview?.equity_curve ?? [])
        .slice(-30)
        .map((p) => p.equity),
    [overview?.equity_curve],
  )
  const todayKey = now.toDateString()
  const todayOrders = paperOrders.filter(
    (o) => new Date(o.time).toDateString() === todayKey,
  )
  const deskInvested = acct?.invested ?? null
  const deskSessions = DESK_SESSIONS.map((id) => MARKET_SESSIONS.find((s) => s.id === id)).filter(
    (s): s is MarketSessionDef => s != null,
  )
  const nowPctUtc = ((now.getUTCHours() + now.getUTCMinutes() / 60) / 24) * 100
  const utcClock = now.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' })
  const nextCloseUtc = nextClose.toLocaleTimeString('fr-FR', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'UTC',
  })
  const regimeText = btcRegime?.summary ?? null
  const kernelText =
    riskPass == null ? (risk?.kernel ? String(risk.kernel).toUpperCase() : null) : riskPass ? 'PASSE' : 'BLOQUÉ'
  const watchSymbols = watchList.map((r) => r.symbol).join(' · ')

  // Pagination (5 / 10 / 20 / 50) appliquée après tri et filtre ; toutes les lignes restent accessibles.
  const pagedPositions = usePaged(positions, 'desk-positions')
  const pagedOrders = usePaged(todayOrders, 'desk-ordres-du-jour')
  const pagedConcentration = usePaged(concentration, 'desk-concentration')
  const pagedTape = usePaged(tape, 'desk-evenements')

  const trajectoryBooks: TrajectoryBook[] = overview
    ? [
        {
          code: MAIN_PORTFOLIO_CODE,
          label: MAIN_PORTFOLIO_LABEL,
          color: MAIN_CURVE_COLOR,
          initialCash: overview.account?.initial_cash ?? null,
          points: overview.equity_curve ?? [],
          openSymbols: (overview.positions ?? []).map((p) => p.symbol),
        },
      ]
    : []

  return (
    <div className="desk-page dk">
      <header className="iv-ph">
        <div>
          <div className="iv-meta">
            Desk · portefeuille paper unique{' '}
            · EUR · {loading && !deskEquity ? '—' : dateLabel || '—'}
          </div>
          <h1>Desk</h1>
          <p>
            Le portefeuille paper unique d’IchiVol · marché · Ève. Le scan, Ève et vos ordres manuels décident pour ce
            seul compte, via le Risk Kernel — jamais live.
          </p>
        </div>
        <div className="iv-ph-act">
          <span className="iv-chip is-cyan">
            <i className="iv-dot dk-dot-cy" />
            Clôture 1H dans {formatCountdown(nextClose, now)}
          </span>
          <span className="iv-chip">
            Régime moteur · <b className="warn">{regimeText ?? '—'}</b>
          </span>
          <Link className="iv-btn" to="/app/portefeuille">
            Portefeuille ↗
          </Link>
          <Link className="iv-btn" to="/app/market">
            Marché ↗
          </Link>
          <Link className="iv-btn" to="/app/agents">
            Ève ↗
          </Link>
        </div>
      </header>

      <div className="iv-kpis dk-kpis">
        <div className="iv-kpi">
          <div className="iv-kpi-k">Capital</div>
          <div className="iv-kpi-v">
            <SplitEur value={deskEquity} />
          </div>
          <div className="iv-kpi-s">
            {acct ? `${MAIN_PORTFOLIO_LABEL} · départ ${fmtEur(acct.initial_cash, 0)}` : '—'}
          </div>
          <Spark values={equitySpark} />
        </div>
        <div className="iv-kpi">
          <div className="iv-kpi-k">Disponible</div>
          <div className="iv-kpi-v">
            <SplitEur value={deskCash} />
          </div>
          <div className="iv-kpi-s">
            {deskCash != null && deskEquity && deskEquity > 0
              ? `${fmtPct(deskCash / deskEquity, 1, false)} du capital`
              : '—'}
          </div>
        </div>
        <div className="iv-kpi">
          <div className="iv-kpi-k">Engagé</div>
          <div className="iv-kpi-v">
            <SplitEur value={invested} />
          </div>
          <div className="iv-kpi-s">
            {investedPct != null ? `${fmtPctPoints(investedPct, 1, false)} du capital` : '—'}
          </div>
        </div>
        <div className="iv-kpi">
          <div className="iv-kpi-k">P&amp;L du jour</div>
          <div className={`iv-kpi-v ${signCls(deskDay)}`.trim()}>{signedEur(deskDay)}</div>
          <div className={`iv-kpi-s ${signCls(dayPct)}`.trim()}>
            {dayPct != null ? `${dayUp ? '↗' : '↘'} ${fmtPct(dayPct)} aujourd’hui` : '—'}
          </div>
        </div>
        <div className="iv-kpi">
          <div className="iv-kpi-k">P&amp;L latent</div>
          <div className={`iv-kpi-v ${signCls(unrealized)}`.trim()}>{signedEur(unrealized)}</div>
          <div className="iv-kpi-s">
            {overview
              ? `${positions.length} position${positions.length > 1 ? 's' : ''}${shortCount > 0 ? ` · ${shortCount} short` : ''}`
              : '—'}
          </div>
        </div>
        <div className="iv-kpi">
          <div className="iv-kpi-k">P&amp;L réalisé</div>
          <div className={`iv-kpi-v ${signCls(acct?.realized_pnl)}`.trim()}>{signedEur(acct?.realized_pnl)}</div>
          <div className="iv-kpi-s">
            {breakdown?.drawdown.max_pct != null
              ? `Drawdown max ${fmtPct(breakdown.drawdown.max_pct, 1, true)}`
              : dd != null
                ? `Drawdown ${fmtPct(dd, 1, true)}`
                : '—'}
          </div>
        </div>
        <div className="iv-kpi">
          <div className="iv-kpi-k">Performance</div>
          <div className={`iv-kpi-v ${signCls(perfPct)}`.trim()}>{perfPct != null ? fmtPct(perfPct, 2) : '—'}</div>
          <div className="iv-kpi-s">
            {acct ? `sur ${fmtEur(acct.initial_cash, 0)} de départ` : '—'}
          </div>
        </div>
        <div className="iv-kpi">
          <div className="iv-kpi-k">Risque utilisé</div>
          <div className="iv-kpi-v">{deskRiskPct != null ? fmtPct(deskRiskPct, 1, false) : '—'}</div>
          <div className="iv-kpi-s">
            {deskRiskMax != null ? `Plafond : ${fmtPct(deskRiskMax, 1, false)}` : '—'}
          </div>
        </div>
      </div>

      {freshnessNotice && (
        <div className="dk-alert" role="status">
          <span aria-hidden="true">△</span>
          <span>
            <b>Cours à vérifier.</b> {freshnessNotice.text}
          </span>
          <Link to={freshnessNotice.href}>Voir la position →</Link>
        </div>
      )}

      <div className="iv-grid">
        <Card
          className="iv-s8 iv-m-s12"
          title="Trajectoire du portefeuille"
          tools={
            <>
              <span>
                Drawdown{' '}
                <b className={dd != null && dd < 0 ? 'neg' : undefined}>{dd != null ? fmtPct(dd, 1, true) : '—'}</b>
              </span>
            </>
          }
        >
          <>
              <div className="dk-traj-bar">
                <span className="iv-cap">
                  Capital <b className="dk-strong">{deskEquity != null ? fmtEur(deskEquity, 2) : '—'}</b>
                </span>
                <div className="iv-seg" role="group" aria-label="Période">
                  {EQUITY_PERIODS.map((p) => (
                    <button
                      key={p}
                      type="button"
                      className={`iv-seg-btn${equityPeriod === p ? ' is-on' : ''}`}
                      aria-pressed={equityPeriod === p}
                      onClick={() => setEquityPeriod(p)}
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </div>
              <EquityTrajectory
                books={trajectoryBooks}
                period={equityPeriod}
                orders={paperOrders}
                deciders={deciderByPosition}
              />
          </>
        </Card>

        <DeskDeciderSummary className="iv-s4 iv-m-s12" />
      </div>

      <div className="iv-grid">
        <Card
          className="iv-s8 iv-m-s12"
          flush
          tabs={
            <>
              <TabButton on={posTab === 'positions'} onClick={() => setPosTab('positions')}>
                Positions ouvertes
              </TabButton>
              <TabButton on={posTab === 'orders'} onClick={() => setPosTab('orders')}>
                Ordres du jour
              </TabButton>
              <TabButton on={posTab === 'concentration'} onClick={() => setPosTab('concentration')}>
                Concentration
              </TabButton>
            </>
          }
          tools={
            <span>
              {positions.length} position{positions.length > 1 ? 's' : ''} ·{' '}
              <b className={signCls(unrealized)}>{signedEur(unrealized)}</b>
            </span>
          }
          foot={
            <>
              <span>Cliquez une ligne pour ouvrir la position</span>
              <Link to="/app/portefeuille">Voir le portefeuille →</Link>
            </>
          }
        >
          {posTab === 'positions' ? (
            positions.length === 0 ? (
              <p className="iv-empty">{loading ? 'Chargement…' : 'Aucune position ouverte.'}</p>
            ) : (
              <div className="iv-table-wrap">
                <table className="iv-table">
                  <thead>
                    <tr>
                      <th>Actif</th>
                      <th>Sens</th>
                      <th>Décideur</th>
                      <th className="n">Qté</th>
                      <th className="n">Entrée</th>
                      <th className="n">Dernier</th>
                      <th className="n">Stop</th>
                      <th className="n">P&amp;L latent</th>
                      <th className="n">R</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pagedPositions.rows.map((p) => {
                      const short = String(p.direction).toUpperCase() === 'SHORT'
                      const pnl = p.unrealized_pnl
                      const r =
                        pnl != null && p.risk_amount != null && p.risk_amount > 0 ? pnl / p.risk_amount : null
                      return (
                        <tr
                          key={p.id ?? p.symbol}
                          className="dk-click"
                          tabIndex={0}
                          onClick={() => openPosition(p.symbol)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault()
                              openPosition(p.symbol)
                            }
                          }}
                        >
                          <td className="sym">
                            {p.symbol}
                            {p.timeframe ? <small>{String(p.timeframe).toUpperCase()}</small> : null}
                            {p.mark_stale ? (
                              <>
                                {' '}
                                <Tag tone="amber">MARK STALE</Tag>
                              </>
                            ) : null}
                          </td>
                          <td>
                            <span className={`iv-side ${short ? 'is-short' : 'is-long'}`}>{short ? 'SHORT' : 'LONG'}</span>
                          </td>
                          <td>
                            <DeciderBadge decider={deciderOf(p)} />
                          </td>
                          <td className="n">{fmtQty(p.qty)}</td>
                          <td className="n">{fmtPrice(p.entry_price)}</td>
                          <td className="n">{fmtPrice(p.current_price)}</td>
                          <td className="n neg">{fmtPrice(p.stop_price)}</td>
                          <td className={`n ${signCls(pnl)}`.trim()}>{signedEur(pnl)}</td>
                          <td className={`n ${signCls(r)}`.trim()}>
                            {r != null ? `${r > 0 ? '+' : r < 0 ? '−' : ''}${fmtDec(Math.abs(r), 1)}` : '—'}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )
          ) : posTab === 'orders' ? (
            todayOrders.length === 0 ? (
              <p className="iv-empty">Aucun ordre aujourd’hui.</p>
            ) : (
              <div className="iv-table-wrap">
                <table className="iv-table is-compact">
                  <thead>
                    <tr>
                      <th>Heure</th>
                      <th>Actif</th>
                      <th>Sens</th>
                      <th>Décideur</th>
                      <th className="n">Qté</th>
                      <th className="n">Prix exécuté</th>
                      <th className="n">Frais</th>
                      <th>Statut</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pagedOrders.rows.map((o) => {
                      const buy = String(o.side).toUpperCase() === 'BUY'
                      return (
                        <tr key={o.id}>
                          <td className="mono dim">{fmtClock(o.time)}</td>
                          <td className="sym">{o.symbol}</td>
                          <td>
                            <span className={`iv-side ${buy ? 'is-long' : 'is-short'}`}>{buy ? 'ACHAT' : 'VENTE'}</span>
                          </td>
                          <td>
                            {o.position_id && deciderByPosition[o.position_id] ? (
                              <DeciderBadge decider={deciderByPosition[o.position_id]!} compact />
                            ) : (
                              <span className="dim">—</span>
                            )}
                          </td>
                          <td className="n">{fmtQty(o.qty)}</td>
                          <td className="n">{fmtPrice(o.filled_price)}</td>
                          <td className="n">{fmtEur(o.fee, 2)}</td>
                          <td>{ORDER_STATUS_FR[String(o.status).toUpperCase()] ?? o.status}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )
          ) : (
            <div className="dk-conc">
              <div className="dk-conc-head">
                <span className="iv-cap">Part de l’exposition par actif</span>
                {concentration.length ? <Tag tone={statusTone(concentrationLabel)}>{concentrationLabel}</Tag> : null}
              </div>
              {concentration.length === 0 ? (
                <p className="iv-empty">—</p>
              ) : (
                pagedConcentration.rows.map((c) => (
                  <button
                    key={c.symbol}
                    type="button"
                    className="iv-row dk-conc-row"
                    onClick={() => openPosition(toEngineSymbol(c.symbol))}
                  >
                    <span className="sym">{c.symbol}</span>
                    <span className={`iv-bar${c.pct >= 40 ? ' is-amber' : ''}`}>
                      <i style={{ width: `${Math.min(100, c.pct)}%` }} />
                    </span>
                    <span className="iv-row-v">{fmtPctPoints(c.pct, 1, false)}</span>
                  </button>
                ))
              )}
              <p className="iv-note">{exposureMixLabel(positions)}</p>
            </div>
          )}
          {posTab === 'positions' ? (
            <TablePager paged={pagedPositions} label="positions" />
          ) : posTab === 'orders' ? (
            <TablePager paged={pagedOrders} label="ordres" />
          ) : (
            <TablePager paged={pagedConcentration} label="actifs" />
          )}
        </Card>

        <DeskEveLatest className="iv-s4 iv-m-s12" />
      </div>

      <div className="iv-grid">
        <Card title="État du système" className="iv-s3 iv-m-s6" bodyClassName="dk-rows">
          <Row
            label="Moteur"
            value={
              engineOk == null ? (
                '—'
              ) : engineOk ? (
                <span className="ok">
                  <i className="iv-dot" /> CONNECTÉ
                </span>
              ) : (
                <span className="dim">
                  <i className="iv-dot is-off" /> NON CONNECTÉ
                </span>
              )
            }
          />
          <Row label="Source des données" value={engineOk ? 'MOTEUR' : rows.length ? 'CACHE' : '—'} />
          <Row label="Régime moteur" value={regimeText ?? '—'} className={regimeText ? 'warn' : ''} />
          <Row
            label="Risk Kernel"
            value={kernelText ?? '—'}
            className={kernelText === 'PASSE' ? 'ok' : kernelText === 'BLOQUÉ' ? 'neg' : ''}
          />
          <Row label="Argent réel" value="JAMAIS · PAPER SEULEMENT" className="dim" />
        </Card>

        <Card
          title="Votre budget de risque"
          className="iv-s3 iv-m-s6"
          tools={kernelText ? <span className={riskPass === false ? 'neg' : 'ok'}>{riskPass === false ? 'BLOQUÉ' : riskPass ? 'PASSE' : kernelText}</span> : null}
          foot={
            <span>
              {acct
                ? `${fmtEur(acct.invested, 2)} engagés sur ${acct.open_positions} positions`
                : '—'}
            </span>
          }
        >
          <Meter
            label="Exposition du capital"
            value={investedPct != null ? fmtPctPoints(investedPct, 1, false) : '—'}
            pct={investedPct}
          />
          <Meter
            label="Risque journalier"
            value={
              risk?.open_risk_pct != null && risk.max_open_risk_pct != null
                ? `${fmtPct(risk.open_risk_pct, 1, false).replace(' %', '')} / ${fmtPct(risk.max_open_risk_pct, 0, false)}`
                : '—'
            }
            pct={dailyRiskPct}
            tone="mint"
          />
          <Meter
            label="Positions simultanées"
            value={risk ? `${risk.open_positions} / ${risk.max_open_positions}` : '—'}
            pct={slotsPct}
          />
          <Meter
            label={concentration[0] ? `Concentration · ${concentration[0].symbol}` : 'Concentration'}
            value={topConc != null ? fmtPctPoints(topConc, 0, false) : '—'}
            pct={topConc}
            tone={topConc != null && topConc >= 40 ? 'amber' : ''}
          />
        </Card>

        <Card
          title="Répartition du capital"
          className="iv-s3 iv-m-s6"
          tools={<span>{deskEquity != null && deskEquity > 0 ? fmtEur(deskEquity, 0) : '—'}</span>}
          foot={<Link to="/app/portefeuille">Voir l’allocation →</Link>}
        >
          {deskEquity == null || deskEquity <= 0 || deskCash == null ? (
            <p className="iv-empty">—</p>
          ) : (
            <>
              <div className="dk-alloc" role="img" aria-label="Part disponible et part engagée du capital">
                <i title={`Disponible · ${fmtEur(deskCash, 0)}`} style={{ width: `${Math.max(0, Math.min(100, (deskCash / deskEquity) * 100))}%`, background: MAIN_CURVE_COLOR }} />
                <i title={`Engagé · ${fmtEur(deskInvested ?? 0, 0)}`} style={{ width: `${Math.max(0, Math.min(100, ((deskInvested ?? 0) / deskEquity) * 100))}%`, background: 'var(--amber, #f5a623)' }} />
              </div>
              <div className="iv-row dk-tight">
                <span>
                  <span className="dk-swatch" style={{ background: MAIN_CURVE_COLOR }} />
                  Disponible
                </span>
                <span className="iv-row-v">{fmtEur(deskCash, 0)}</span>
              </div>
              <div className="iv-row dk-tight">
                <span>
                  <span className="dk-swatch" style={{ background: 'var(--amber, #f5a623)' }} />
                  Engagé
                </span>
                <span className="iv-row-v">{deskInvested != null ? fmtEur(deskInvested, 0) : '—'}</span>
              </div>
            </>
          )}
        </Card>

        <Card
          title="Sessions de marché"
          className="iv-s3 iv-m-s6"
          tools={
            <span>
              <span className={openSessions > 0 ? 'ok' : undefined}>
                {openSessions} ouverte{openSessions > 1 ? 's' : ''}
              </span>{' '}
              · {utcClock} UTC
            </span>
          }
          foot={
            <span className="dk-sess-detail">
              <b>
                {selectedSession.city} · {selectedSession.venue}
              </b>{' '}
              · {formatVenueClock(selectedSession, now)} locale · {formatSessionHoursUtc(selectedSession, now)}
              {nextOpen
                ? ` · ouverture dans ${formatCountdown(nextOpen, now)}`
                : selectedSession.kind === 'always'
                  ? ' · sans clôture'
                  : ''}
              {' '}· <span className={selectedSt === 'open' ? 'ok' : 'dim'}>{sessionStatusLabel(selectedSt)}</span>
            </span>
          }
        >
          <div className="dk-sessions">
            {deskSessions.map((s) => {
              const st = sessionStatus(s, now)
              return (
                <button
                  key={s.id}
                  type="button"
                  className={`iv-dk-sess${sessionId === s.id ? ' is-sel' : ''}`}
                  aria-pressed={sessionId === s.id}
                  onClick={() => setSessionId(s.id)}
                >
                  <span className="dk-sess-name">{s.region}</span>
                  <span className="dk-sess-track" aria-hidden="true">
                    {sessionSegments(s, now).map(([a, b]) => (
                      <i
                        key={`${a}-${b}`}
                        className={st === 'open' ? 'is-open' : undefined}
                        style={{ left: `${a}%`, width: `${Math.max(0.5, b - a)}%` }}
                      />
                    ))}
                    <b style={{ left: `${nowPctUtc}%` }} />
                  </span>
                  <Tag tone={sessionTone(st)}>{sessionStatusLabel(st)}</Tag>
                </button>
              )
            })}
            <div className="dk-sess-axis" aria-hidden="true">
              <i />
              <span>
                <em>00:00</em>
                <em>12:00</em>
                <em>24:00</em>
              </span>
              <i>UTC</i>
            </div>
          </div>
        </Card>
      </div>

      <div className="iv-grid">
        <Card
          title="À surveiller"
          className="iv-s5 iv-m-s12"
          flush
          tools={<span>Ichimoku × RVOL</span>}
          foot={<Link to="/app/opportunites">Explorer les opportunités →</Link>}
        >
          {watchList.length === 0 ? (
            <p className="iv-empty">{loading ? 'Chargement…' : 'Aucune sélection pour l’instant.'}</p>
          ) : (
            <div className="iv-table-wrap">
              <table className="iv-table is-compact">
                <thead>
                  <tr>
                    <th>Actif</th>
                    <th>Cycle</th>
                    <th>Lecture</th>
                    <th className="n">RVOL</th>
                    <th className="n">Conf.</th>
                  </tr>
                </thead>
                <tbody>
                  {watchList.map((r) => (
                    <tr
                      key={r.symbol}
                      className="dk-click"
                      tabIndex={0}
                      onClick={() => openOpp(r.symbol)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          openOpp(r.symbol)
                        }
                      }}
                    >
                      <td className="sym">{r.symbol}</td>
                      <td>
                        <Tag tone={decisionTone(r)}>{r.decision ? decisionFr(String(r.decision)) : '—'}</Tag>
                      </td>
                      <td className="dk-ellipsis">{opportunityCaption(r)}</td>
                      <td className={`n ${r.rvol != null && r.rvol >= RVOL_THRESHOLD ? 'ok' : ''}`.trim()}>
                        {r.rvol != null ? fmtDec(r.rvol, 2) : '—'}
                      </td>
                      <td className="n">
                        {r.confidence != null && Number.isFinite(r.confidence) ? fmtDec(r.confidence, 2) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card
          title="Marchés principaux"
          className="iv-s4 iv-m-s6"
          flush
          tools={
            <span className={rows.length === 0 ? '' : marketsStale ? 'warn' : 'ok'}>
              {rows.length === 0 ? '24 H' : marketsStale ? 'RETARD' : 'COURS · 24 H'}
            </span>
          }
          foot={<Link to="/app/market">Tout le marché →</Link>}
        >
          {primaryMarkets.length === 0 ? (
            <p className="iv-empty">—</p>
          ) : (
            <div className="iv-table-wrap">
              <table className="iv-table">
                <tbody>
                  {primaryMarkets.map((r) => {
                    const base = r.symbol.replace(/USDT$/i, '')
                    const chg = changeBySymbol[r.symbol.toUpperCase()]
                    const has = chg != null && !Number.isNaN(chg)
                    return (
                      <tr
                        key={r.symbol}
                        className="dk-click"
                        tabIndex={0}
                        onClick={() => openMarket(r.symbol)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            openMarket(r.symbol)
                          }
                        }}
                      >
                        <td className="sym">
                          {base}
                          <small>/ USDT</small>
                        </td>
                        <td className="muted dk-small">{r.decision ? decisionFr(String(r.decision)) : '—'}</td>
                        <td className="n">{fmtPrice(r.price)}</td>
                        <td className={`n ${has ? signCls(chg) : ''}`.trim()}>
                          {has ? fmtPctPoints(chg, 2, true) : '—'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card
          title="Lecture du marché"
          className="iv-s3 iv-m-s6"
          foot={<Link to="/app/context">Ouvrir le contexte →</Link>}
        >
          <div className="iv-cap">Indice Fear &amp; Greed · crypto</div>
          <div className="dk-fng">
            <span className={`dk-fng-v${fng ? (fng.value >= 55 ? ' warn' : fng.value <= 45 ? ' cy' : '') : ''}`}>
              {fng ? fng.value : '—'}
            </span>
            <div>
              <div className="dk-strong">{fng ? fearGreedFr(fng.classification) : 'Indice indisponible'}</div>
              <div className="muted dk-small">
                {climateSymbol} {fng ? 'avidité ou peur, sur 100' : '—'}
              </div>
            </div>
          </div>
          <Row label="Dominance BTC" value={btcDom ? fmtPctPoints(btcDom.percent, 1, false) : '—'} />
          <Row
            label="Volume relatif BTC"
            value={btcRow?.rvol != null ? `${fmtDec(btcRow.rvol, 2)} ×` : '—'}
            className={btcRow?.rvol != null && btcRow.rvol >= RVOL_THRESHOLD ? 'ok' : ''}
          />
          <Row
            label="Concentration"
            value={concentrationLabel === '—' ? '—' : <Tag tone={statusTone(concentrationLabel)}>{concentrationLabel}</Tag>}
          />
          <p className="iv-note dk-mt">
            {fng ? 'Ce n’est pas un régime calculé par IchiVol. ' : ''}Le contexte éclaire le signal. Le risque garde le
            dernier mot.
          </p>
        </Card>
      </div>

      <div className="iv-grid">
        <Card
          title="Derniers événements"
          className="iv-s8 iv-m-s12"
          flush
          tools={<span>Journal d’audit</span>}
          foot={<Link to="/app/operations">Toutes les opérations →</Link>}
        >
          {tape.length === 0 ? (
            <p className="iv-empty">{loading ? 'Chargement…' : '—'}</p>
          ) : (
            <div className="iv-table-wrap">
              <table className="iv-table is-compact">
                <thead>
                  <tr>
                    <th>Heure</th>
                    <th>Niveau</th>
                    <th>Source</th>
                    <th>Événement</th>
                  </tr>
                </thead>
                <tbody>
                  {pagedTape.rows.map((it) => {
                    const level = FEED_LEVEL[it.tone] ?? FEED_LEVEL.neutral
                    const detail = (it.detail || '').replace(/\s+/g, ' ').trim()
                    return (
                      <tr key={`${it.time}-${it.kind}-${it.symbol}-${it.portfolio}-${it.detail}`}>
                        <td className="mono dim">{fmtClock(it.time)}</td>
                        <td>
                          <Tag tone={level.tone}>{level.label}</Tag>
                        </td>
                        <td>{it.portfolio || '—'}</td>
                        <td className="dk-event">
                          {it.title}
                          {detail ? <span className="muted"> · {detail}</span> : null}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
          <TablePager paged={pagedTape} label="événements" />
        </Card>

        <Card
          title="Le prochain contrôle"
          className="iv-s4 iv-m-s12"
          glow
          foot={<Link to="/app/opportunites">Examiner les confirmations →</Link>}
        >
          <div className="iv-meta">Clôture de la bougie 1H · {nextCloseUtc} UTC</div>
          <div className="dk-countdown">{formatCountdown(nextClose, now)}</div>
          <p className="iv-note">
            Le volume reste à confirmer sur BTC. La confiance ne remplace pas les{' '}
            <span className="iv-kw">portes de décision</span>.
          </p>
          <Row
            label="BTC · participation"
            value={
              btcRow?.rvol != null ? (
                <Tag tone={btcRow.rvol >= RVOL_THRESHOLD ? 'mint' : 'amber'}>RVOL {fmtDec(btcRow.rvol, 1)}×</Tag>
              ) : (
                '—'
              )
            }
          />
          <Row label="Seuil attendu" value={`≥ ${fmtDec(RVOL_THRESHOLD, 1)}×`} />
          <div className="dk-chips">
            <span className="iv-chip">
              {watchList.length} à surveiller
            </span>
            {watchSymbols ? <span className="iv-chip is-amber">{watchSymbols}</span> : null}
          </div>
        </Card>
      </div>
    </div>
  )
}
