/**
 * Desk — port littéral de design-reference/ichivol-workspace `desk()` + page-head.
 * Classes HTML = maquette. Données = engine (pas de démo inventée ; manquant → « — »).
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
  type SessionId,
  type SessionStatus,
} from '../lib/marketSessions'
import {
  type PaperOrderRow,
  type PaperOverview,
  type PaperOverviewPosition,
} from '../lib/paper'
import { type RiskLockState } from '../lib/riskLock'
import {
  combineLocks,
  combineOverviews,
  listActiveBooks,
  loadAllActivity,
  loadAllBooks,
  type BookPosition,
} from '../lib/allBooks'
import { verdictBucket } from '../lib/deskSummarize'
import {
  aggregateDeskBooks,
  concentrationFromPositions,
  snapshotFromOverview,
  type DeskBooksAggregate,
} from '../components/desk/deskMetrics'
import {
  BASELINE,
  PRIMARY_SYMBOLS,
  REFRESH_MS,
  TAPE_LIMIT,
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
import { bookColors, cleanEquitySeries } from '../components/desk/equityTrajectory'
import './OverviewPage.css'

const RING_COLORS = ['#548f87', '#8c9eb4', '#c2b596', '#a9bdb2', '#7d8288'] as const
const RVOL_THRESHOLD = 1.5
const EQUITY_PERIODS: EquityPeriod[] = ['1J', '1S', '1M', '3M']

type BadgeTone = 'green' | 'amber' | 'red' | 'gray' | ''

function badge(text: string, tone: BadgeTone = ''): ReactNode {
  const inferred: BadgeTone =
    tone ||
    (/PASSE|ACCEPTÉ|OUVERTE|VALIDÉ|CONNECTÉ/.test(text)
      ? 'green'
      : /REFUS|BLOQU|ERREUR|HORS/.test(text)
        ? 'red'
        : /PRUDENCE|TRIGGERED/.test(text)
          ? 'amber'
          : '')
  return <span className={`tag ${inferred}`.trim()}>{text}</span>
}

function DeskCard({
  title,
  extra,
  className = '',
  children,
}: {
  title: string
  extra?: ReactNode
  className?: string
  children: ReactNode
}) {
  return (
    <section className={`card ${className}`.trim()}>
      <div className="card-head">
        <h2>{title}</h2>
        {extra}
      </div>
      {children}
    </section>
  )
}

function StatLine({ label, value }: { label: ReactNode; value: ReactNode }) {
  return (
    <div className="statline">
      <span>{label}</span>
      <b>{value}</b>
    </div>
  )
}

function ProgressRow({
  label,
  value,
  pct,
  warn = false,
}: {
  label: string
  value: string
  pct: number
  warn?: boolean
}) {
  const width = Math.max(0, Math.min(100, pct))
  return (
    <>
      <div className="risk-row">
        <span>{label}</span>
        <span className={`mono ${warn ? 'warn' : ''}`.trim()}>{value}</span>
      </div>
      <div className="track">
        <span
          style={
            warn
              ? { width: `${width}%`, background: '#b99557' }
              : { width: `${width}%` }
          }
        />
      </div>
    </>
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

function sessionTone(st: SessionStatus): string {
  switch (st) {
    case 'open':
      return 'is-open'
    case 'upcoming':
      return 'is-soon'
    case 'closed':
      return 'is-closed'
    default: {
      const _e: never = st
      return _e
    }
  }
}

function sessionStatusClass(st: SessionStatus): string {
  switch (st) {
    case 'open':
      return 'up'
    case 'closed':
    case 'upcoming':
      return 'muted'
    default: {
      const _e: never = st
      return _e
    }
  }
}

function coinLetter(sym: string): { letter: string; cls: string } {
  const s = sym.replace(/USDT$/i, '').toUpperCase()
  if (s === 'BTC') return { letter: '₿', cls: '' }
  if (s === 'ETH') return { letter: 'Ξ', cls: 'eth' }
  if (s === 'SOL') return { letter: 'S', cls: 'sol' }
  return { letter: s.slice(0, 1), cls: s === 'LINK' ? 'eth' : '' }
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

function decisionBadgeText(r: ScreenerDecisionRow): string {
  const d = String(r.decision ?? '').toUpperCase()
  if (!d) return '—'
  return d
}

export function OverviewPage() {
  const navigate = useNavigate()
  const [rows, setRows] = useState<ScreenerDecisionRow[]>([])
  const [loading, setLoading] = useState(true)
  const [overview, setOverview] = useState<PaperOverview | null>(null)
  const [booksAgg, setBooksAgg] = useState<DeskBooksAggregate | null>(null)
  const [bookCurves, setBookCurves] = useState<TrajectoryBook[]>([])
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

  const load = useCallback(async (force = false) => {
    setLoading(true)
    type ScreenerOk = Awaited<ReturnType<typeof getScreener>>
    // Desk = tous les portefeuilles paper actifs : totaux, positions, ordres, verrous.
    const booksPromise = listActiveBooks()
      .then(async (rows) => {
        const books = await loadAllBooks(rows)
        const orders = await loadAllActivity(books, 200)
        return {
          rows,
          books,
          orders,
          agg: aggregateDeskBooks(books.map((b) => snapshotFromOverview(b.code, b.label, b.overview))),
          curves: (() => {
            const colors = bookColors(books.map((b) => b.code))
            return books.map(
              (b) =>
                ({
                  code: b.code,
                  label: b.label,
                  color: colors[b.code]!,
                  initialCash: b.overview.account?.initial_cash ?? null,
                  points: b.overview.equity_curve ?? [],
                  openSymbols: (b.overview.positions ?? []).map((p) => p.symbol),
                }) satisfies TrajectoryBook,
            )
          })(),
        }
      })
      .catch(() => null)

    const [screenerRes, ovRes, booksRes, feedRes, ordersRes, lockRes, healthRes, mktRes, fngRes, tickersRes] =
      await Promise.all([
        getScreener('1h', force)
          .then((r): ScreenerOk | Error => r)
          .catch((err: unknown): ScreenerOk | Error =>
            err instanceof Error ? err : new Error('Screener indisponible'),
          ),
        booksPromise.then((b) => {
          const combined = b ? combineOverviews(b.books) : null
          return combined ? { ok: true as const, data: combined } : { ok: false as const }
        }),
        booksPromise,
        getActivityFeed(100)
          .then((r) => ({ ok: true as const, items: r.items }))
          .catch(() => ({ ok: false as const, items: [] as ActivityItem[] })),
        booksPromise.then((b) =>
          b ? { ok: true as const, orders: b.orders as PaperOrderRow[] } : { ok: false as const, orders: [] as PaperOrderRow[] },
        ),
        booksPromise.then((b) => (b ? combineLocks(b.rows) : null)),
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

    if (booksRes) {
      setBooksAgg(booksRes.agg)
      setBookCurves(booksRes.curves)
    } else {
      setBooksAgg(null)
      setBookCurves([])
    }

    if (feedRes.ok) {
      setTape(feedRes.items.slice(0, TAPE_LIMIT))
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
  /** Totaux Desk = tous les livres paper ; fallback baseline si liste vide. */
  const deskEquity = booksAgg?.book_count ? booksAgg.equity : acct?.equity
  const deskCash = booksAgg?.book_count ? booksAgg.cash : acct?.cash
  const deskDay = booksAgg?.book_count ? booksAgg.day_change : acct?.day_change
  const deskRiskPct = booksAgg?.book_count ? booksAgg.open_risk_pct : risk?.open_risk_pct
  const deskRiskMax = booksAgg?.book_count
    ? booksAgg.max_open_risk_pct
    : risk?.max_open_risk_pct
  const deskBookCount = booksAgg?.book_count ?? (overview ? 1 : 0)
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
      .slice(0, 3)
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
  const concentrationTone: BadgeTone =
    topConc == null ? '' : topConc >= 40 ? 'amber' : 'green'
  const concentrationLabel =
    topConc == null ? '—' : topConc >= 40 ? 'PRUDENCE' : 'ÉQUILIBRÉ'

  const climateSymbol =
    fng == null ? '—' : fng.value >= 55 ? '↗' : fng.value <= 45 ? '↘' : '→'
  const climateTitle = fng ? `${fearGreedFr(fng.classification)} · ${fng.value}` : '—'
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

  return (
    <div className="desk-page">
      <div className="page-head">
        <div>
          <div className="eyebrow">01 / ICHIVOL WORKSPACE</div>
          <h1>Desk</h1>
          <p className="subtitle">
            Tous les portefeuilles paper réunis · marché · Ève.
          </p>
        </div>
        <div className="actions">
          <span className="subtitle">{loading && !deskEquity ? '—' : dateLabel || '—'}</span>
          <Link className="link" to="/app/portefeuille" style={{ marginLeft: 14 }}>
            Portefeuilles ↗
          </Link>
          <Link className="link" to="/app/market" style={{ marginLeft: 14 }}>
            Marché ↗
          </Link>
          <Link className="link" to="/app/agents" style={{ marginLeft: 14 }}>
            Ève ↗
          </Link>
        </div>
      </div>

      <div className="notice">
        ⬡{' '}
        <span>
          Desk = agrégat de tous les livres paper. Ève peut trader paper (autonomie on) via Risk
          Kernel — jamais live.
        </span>
      </div>

      <div className="desk-workspace">
        <div className="metrics">
          <div className="metric featured">
            <div className="metric-label">
              Capital total<span>↗</span>
            </div>
            <div className="metric-value">
              {deskEquity != null ? fmtEur(deskEquity, 2) : '—'}
            </div>
            <small>
              {deskBookCount > 0
                ? `${deskBookCount} livre${deskBookCount > 1 ? 's' : ''} paper · EUR`
                : 'Portefeuilles paper · EUR'}
            </small>
          </div>
          <div className="metric">
            <div className="metric-label">
              Disponible<span>↗</span>
            </div>
            <div className="metric-value">
              {deskCash != null ? fmtEur(deskCash, 2) : '—'}
            </div>
            <small>
              {deskCash != null && deskEquity && deskEquity > 0
                ? `${fmtPct(deskCash / deskEquity, 1, false)} du capital`
                : '—'}
            </small>
          </div>
          <div className={`metric${dayUp ? ' up' : ''}`.trim()}>
            <div className="metric-label">
              P&amp;L du jour<span>↗</span>
            </div>
            <div className="metric-value">
              {deskDay != null ? fmtEur(deskDay, 2) : '—'}
            </div>
            <small>
              {dayPct != null ? `${dayUp ? '↗' : '↘'} ${fmtPct(dayPct)} aujourd’hui` : '—'}
            </small>
          </div>
          <div className="metric">
            <div className="metric-label">
              Risque utilisé<span>↗</span>
            </div>
            <div className="metric-value">
              {deskRiskPct != null ? fmtPct(deskRiskPct, 1, false) : '—'}
            </div>
            <small>
              {deskRiskMax != null
                ? `Plafond global : ${fmtPct(deskRiskMax, 1, false)}`
                : '—'}
            </small>
          </div>
        </div>

        {booksAgg && booksAgg.books.length > 0 ? (
          <section className="card desk-books" aria-label="Tous les portefeuilles paper">
            <div className="card-head">
              <h2>Portefeuilles virtuels</h2>
              {badge(`${booksAgg.books.length} LIVRES`, 'gray')}
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>LIVRE</th>
                    <th>EQUITY</th>
                    <th>CASH</th>
                    <th>P&amp;L JOUR</th>
                    <th>RISQUE</th>
                    <th>POS.</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {booksAgg.books.map((b) => (
                    <tr key={b.code}>
                      <td>
                        <b>{b.label}</b>
                        <small>{b.code}</small>
                      </td>
                      <td className="mono">{fmtEur(b.equity, 2)}</td>
                      <td className="mono">{fmtEur(b.cash, 2)}</td>
                      <td className="mono">
                        {b.day_change != null ? fmtEur(b.day_change, 2) : '—'}
                      </td>
                      <td className="mono">
                        {b.open_risk_pct != null
                          ? fmtPct(b.open_risk_pct, 1, false)
                          : '—'}
                      </td>
                      <td>{b.open_positions}</td>
                      <td>
                        <Link
                          className="link"
                          to={`/app/portefeuille?pf=${encodeURIComponent(b.code)}`}
                        >
                          Ouvrir ↗
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        ) : null}

        <div className="desk-overview">
          <DeskCard
            title="Sessions de marché"
            extra={badge(
              openSessions > 0 ? `${openSessions} OUVERTE${openSessions > 1 ? 'S' : ''}` : 'FERMÉES',
              openSessions > 0 ? 'green' : 'gray',
            )}
            className="world-card"
          >
            <div className="world-view">
              <img
                src="/world-map.svg"
                alt="Carte des places : Sydney, Asie, Europe, New York, Chicago"
                width={720}
                height={290}
              />
              {MARKET_SESSIONS.filter((s) => s.kind !== 'always').map((s) => {
                const st = sessionStatus(s, now)
                return (
                <button
                  key={s.id}
                  type="button"
                  className={`map-marker${sessionId === s.id ? ' selected' : ''}${st === 'open' ? ' is-open' : ''}`}
                  style={{ left: `${s.mapLeftPct}%`, top: `${s.mapTopPct}%` }}
                  aria-label={`Session ${s.city}`}
                  aria-pressed={sessionId === s.id}
                  onClick={() => setSessionId(s.id)}
                >
                  <span />
                  {sessionId === s.id ? <b>{s.city}</b> : null}
                </button>
                )
              })}
            </div>
            <div className="session-selector">
              {MARKET_SESSIONS.map((s) => {
                const st = sessionStatus(s, now)
                return (
                  <button
                    key={s.id}
                    type="button"
                    className={sessionId === s.id ? 'active' : ''}
                    aria-pressed={sessionId === s.id}
                    onClick={() => setSessionId(s.id)}
                  >
                    {s.region}
                    <small className={sessionTone(st)}>{sessionStatusLabel(st)}</small>
                  </button>
                )
              })}
            </div>
            <div id="desk-session-detail" className="session-detail">
              <strong>
                {selectedSession.city} · {selectedSession.venue}{' '}
                <span className={sessionStatusClass(selectedSt)}>
                  {sessionStatusLabel(selectedSt)}
                </span>
              </strong>
              <span className="mono">
                {formatVenueClock(selectedSession, now)} locale · {formatSessionHoursUtc(selectedSession, now)}
              </span>
              {nextOpen ? (
                <span>Prochaine ouverture dans {formatCountdown(nextOpen, now)}</span>
              ) : selectedSession.kind === 'always' ? (
                <span>Sans clôture</span>
              ) : null}
            </div>
            <div className="map-foot">
              Cash, futures CME et crypto. Le vendredi soir en Europe, l’Asie, Londres et New York sont déjà fermés.
            </div>
          </DeskCard>

          <DeskCard
            title="Marchés principaux"
            extra={badge(
              rows.length === 0 ? '—' : marketsStale ? 'RETARD' : 'COURS',
              rows.length === 0 ? 'gray' : marketsStale ? 'amber' : 'green',
            )}
          >
            <div className="desk-tickers">
              {primaryMarkets.map((r) => {
                const base = r.symbol.replace(/USDT$/i, '')
                const chg = changeBySymbol[r.symbol.toUpperCase()]
                const chgCls =
                  chg == null || Number.isNaN(chg) ? '' : chg > 0 ? 'up' : chg < 0 ? 'down' : ''
                return (
                  <button
                    key={r.symbol}
                    type="button"
                    className="desk-ticker"
                    onClick={() => openMarket(r.symbol)}
                  >
                    <span>
                      <b>
                        {base}
                        <small> / USDT</small>
                      </b>
                      <small>{r.decision ? decisionFr(String(r.decision)) : '—'}</small>
                    </span>
                    <span className="right">
                      <b className="mono">{fmtPrice(r.price)}</b>
                      <small className={chgCls}>
                        {chg == null || Number.isNaN(chg)
                          ? '—'
                          : fmtPctPoints(chg, 2, true)}
                      </small>
                    </span>
                  </button>
                )
              })}
            </div>
            <div className="card-foot">
              <Link to="/app/market" className="link">
                Tout le marché ↗
              </Link>
            </div>
          </DeskCard>

          <DeskCard title="Lecture du marché">
            <div className="card-body">
              <div className="climate-head">
                <span className="climate-symbol">{climateSymbol}</span>
                <div>
                  <small>INDICE FEAR &amp; GREED · CRYPTO</small>
                  <h3>{climateTitle}</h3>
                </div>
              </div>
              <p className="desk-note">
                {fng
                  ? `Avidité ou peur du marché crypto, sur 100. Ce n’est pas un régime calculé par IchiVol.`
                  : 'Indice crypto indisponible.'}
              </p>
              <StatLine
                label="Volume relatif BTC"
                value={btcRow?.rvol != null ? `${btcRow.rvol.toFixed(2)}×` : '—'}
              />
              <StatLine label="Régime moteur" value={btcRegime?.summary ?? '—'} />
              <StatLine
                label="Dominance BTC"
                value={btcDom ? fmtPctPoints(btcDom.percent, 1, false) : '—'}
              />
              <StatLine
                label="Concentration"
                value={
                  concentrationLabel === '—'
                    ? '—'
                    : badge(concentrationLabel, concentrationTone)
                }
              />
              <p className="desk-note">
                Le contexte éclaire le signal. Le risque garde le dernier mot.
              </p>
              <Link to="/app/context" className="link">
                Ouvrir le contexte ↗
              </Link>
            </div>
          </DeskCard>
        </div>

        <div className="grid">
          <DeskCard
            title="Trajectoire des portefeuilles"
            extra={
              <div className="segmented">
                {EQUITY_PERIODS.map((p) => (
                  <button
                    key={p}
                    type="button"
                    className={equityPeriod === p ? 'active' : ''}
                    onClick={() => setEquityPeriod(p)}
                  >
                    {p}
                  </button>
                ))}
              </div>
            }
          >
            <div className="chart-summary">
              <span>
                CAPITAL TOTAL{' '}
                <b>{deskEquity != null ? fmtEur(deskEquity, 2) : '—'}</b>
              </span>
              <span>
                LIVRES <b>{bookCurves.length || deskBookCount || '—'}</b>
              </span>
              <span>
                DRAWDOWN{' '}
                <b className={dd != null && dd < 0 ? 'down' : undefined}>
                  {dd != null ? fmtPct(dd, 1, true) : '—'}
                </b>
              </span>
            </div>
            <EquityTrajectory
              books={
                bookCurves.length > 0
                  ? bookCurves
                  : overview
                    ? [
                        {
                          code: BASELINE,
                          label: 'IchiVol',
                          color: bookColors([BASELINE])[BASELINE]!,
                          initialCash: overview.account?.initial_cash ?? null,
                          points: overview.equity_curve ?? [],
                          openSymbols: (overview.positions ?? []).map((p) => p.symbol),
                        },
                      ]
                    : []
              }
              period={equityPeriod}
              orders={paperOrders}
            />
          </DeskCard>

          <DeskCard
            title="À surveiller"
            extra={badge(
              watchList.length ? `${watchList.length} SÉLECTIONS` : '—',
              'gray',
            )}
          >
            <div className="card-body">
              {watchList.map((r) => {
                const base = r.symbol.replace(/USDT$/i, '')
                const coin = coinLetter(base)
                const score =
                  r.confidence != null && Number.isFinite(r.confidence)
                    ? Math.round(r.confidence * 100)
                    : null
                return (
                  <div
                    key={r.symbol}
                    className="opportunity"
                    tabIndex={0}
                    role="button"
                    onClick={() => openOpp(r.symbol)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        openOpp(r.symbol)
                      }
                    }}
                  >
                    <span className={`coin ${coin.cls}`.trim()}>{coin.letter}</span>
                    <div>
                      <strong>
                        {base}
                        <span style={{ color: '#a0a4a6', fontWeight: 400 }}> / USDT</span>
                      </strong>
                      <small>{opportunityCaption(r)}</small>
                    </div>
                    <div className="right">
                      <span className="score">
                        {score != null ? score : '—'}
                        <small style={{ display: 'inline' }}> /100</small>
                      </span>
                      <small>{badge(decisionBadgeText(r))}</small>
                    </div>
                  </div>
                )
              })}
            </div>
            <div className="card-foot">
              <Link className="link" to="/app/opportunites">
                Explorer les opportunités ↗
              </Link>
            </div>
          </DeskCard>
        </div>

        {freshnessNotice && (
          <div className="notice">
            <span>△</span>
            <span>
              <b>Cours à vérifier.</b> {freshnessNotice.text}
            </span>
            <Link to={freshnessNotice.href}>Voir la position →</Link>
          </div>
        )}

        <div className="grid">
          <DeskCard
            title="Positions ouvertes"
            extra={
              <Link className="link" to="/app/portefeuille">
                Portefeuille ↗
              </Link>
            }
          >
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>ACTIF / STRATÉGIE</th>
                    <th>ENGAGÉ</th>
                    <th>PERFORMANCE</th>
                    <th>P&amp;L LATENT</th>
                    <th>ÉTAT</th>
                  </tr>
                </thead>
                <tbody>
                  {(overview?.positions ?? []).slice(0, 3).map((p: PaperOverviewPosition & Partial<BookPosition>) => {
                    const base = p.symbol.replace(/USDT$/i, '')
                    const engaged =
                      p.market_value ??
                      (p.current_price != null && p.qty != null
                        ? p.current_price * Math.abs(p.qty)
                        : p.notional ?? null)
                    const perf = p.unrealized_pct
                    const pnl = p.unrealized_pnl
                    const perfCls =
                      perf == null ? '' : perf > 0 ? 'up' : perf < 0 ? 'down' : ''
                    const pnlCls =
                      pnl == null ? '' : pnl > 0 ? 'up' : pnl < 0 ? 'down' : ''
                    const strat =
                      p.timeframe != null
                        ? `${p.book_label ? `${p.book_label} · ` : ''}Ichimoku × RVOL · ${String(p.timeframe).toUpperCase()}`
                        : '—'
                    return (
                      <tr
                        key={p.id ?? p.symbol}
                        className="clickable"
                        tabIndex={0}
                        onClick={() => openPosition(p.symbol)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            openPosition(p.symbol)
                          }
                        }}
                      >
                        <td>
                          <b>{base}</b>
                          <small>{strat}</small>
                        </td>
                        <td>
                          <span className="mono">{fmtEur(engaged, 2)}</span>
                        </td>
                        <td>
                          <span className={`mono ${perfCls}`.trim()}>
                            {perf != null ? fmtPct(perf, 2, true) : '—'}
                          </span>
                        </td>
                        <td>
                          <span className={`mono ${pnlCls}`.trim()}>
                            {fmtEur(pnl, 2)}
                          </span>
                        </td>
                        <td>{badge(p.mark_stale ? 'MARK STALE' : 'OUVERTE')}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </DeskCard>

          <DeskCard
            title="Votre budget de risque"
            extra={
              riskPass == null
                ? badge('—', 'gray')
                : riskPass
                  ? badge('PASSE')
                  : badge('BLOQUÉ', 'red')
            }
          >
            <div className="card-body">
              <ProgressRow
                label="Exposition du capital"
                value={investedPct != null ? fmtPctPoints(investedPct, 1, false) : '—'}
                pct={investedPct ?? 0}
              />
              <ProgressRow
                label="Risque journalier"
                value={
                  risk?.open_risk_pct != null && risk.max_open_risk_pct != null
                    ? `${fmtPct(risk.open_risk_pct, 1, false).replace(' %', '')} / ${fmtPct(risk.max_open_risk_pct, 0, false)}`
                    : '—'
                }
                pct={dailyRiskPct ?? 0}
              />
              <ProgressRow
                label="Positions simultanées"
                value={
                  risk
                    ? `${risk.open_positions} / ${risk.max_open_positions}`
                    : '—'
                }
                pct={slotsPct ?? 0}
              />
              <div style={{ marginTop: 20, fontSize: 10, color: 'var(--muted)' }}>
                {acct
                  ? `${fmtEur(acct.invested, 2)} engagés sur ${acct.open_positions} positions.`
                  : '—'}
              </div>
            </div>
          </DeskCard>
        </div>

        <div className="grid three">
          <DeskCard title="Derniers événements">
            <div className="card-body">
              <div className="timeline">
                {tape.length === 0 ? (
                  <div className="event">
                    —<small>—</small>
                  </div>
                ) : (
                  tape.slice(0, 3).map((it) => {
                    const detail = (it.detail || '—').replace(/\s+/g, ' ').trim()
                    const short =
                      detail.length > 36 ? `${detail.slice(0, 34)}…` : detail
                    const title =
                      it.title.length > 42 ? `${it.title.slice(0, 40)}…` : it.title
                    return (
                      <div
                        key={`${it.time}-${it.kind}-${it.symbol}-${it.portfolio}-${it.detail}`}
                        className="event"
                      >
                        {title}
                        <small>
                          {fmtClock(it.time)} · {short}
                        </small>
                      </div>
                    )
                  })
                )}
              </div>
            </div>
          </DeskCard>

          <DeskCard title="Le prochain contrôle">
            <div className="card-body">
              <div className="checkpoint">
                <span className="checkpoint-icon">◇</span>
                <div>
                  <b>Clôture 1H</b>
                  <small>
                    {formatCountdown(nextClose, now)} · {fmtClock(nextClose.toISOString())}
                  </small>
                </div>
              </div>
              <StatLine
                label="BTC · participation"
                value={
                  btcRow?.rvol != null
                    ? badge(
                        `RVOL ${fmtDec(btcRow.rvol, 1)}×`,
                        btcRow.rvol >= RVOL_THRESHOLD ? 'green' : 'amber',
                      )
                    : '—'
                }
              />
              <StatLine label="Seuil attendu" value={`≥ ${fmtDec(RVOL_THRESHOLD, 1)}×`} />
              <p className="desk-note">
                Le volume reste à confirmer sur BTC. La confiance ne remplace pas les portes de
                décision.
              </p>
              <Link className="link" to="/app/opportunites">
                Examiner les confirmations →
              </Link>
            </div>
          </DeskCard>

          <DeskCard title="État du système">
            <div className="card-body">
              <StatLine
                label="Moteur Python"
                value={
                  engineOk == null
                    ? '—'
                    : engineOk
                      ? badge('CONNECTÉ')
                      : badge('NON CONNECTÉ', 'gray')
                }
              />
              <StatLine
                label="Source des données"
                value={
                  engineOk
                    ? badge('ENGINE', 'gray')
                    : rows.length
                      ? badge('CACHE', 'gray')
                      : '—'
                }
              />
              <StatLine
                label="Risk Kernel"
                value={
                  riskPass == null
                    ? risk?.kernel
                      ? badge(String(risk.kernel).toUpperCase(), 'gray')
                      : '—'
                    : riskPass
                      ? badge('PASSE')
                      : badge('BLOQUÉ', 'red')
                }
              />
              <StatLine label="Exécution réelle" value={badge('BLOQUÉE', 'red')} />
            </div>
          </DeskCard>
        </div>

        <div className="desk-allocation">
          <DeskCard
            title="Répartition du capital"
            extra={badge(acct ? fmtEur(acct.equity, 0) : '—', 'gray')}
          >
            <div className="allocation-body">
              <div className="desk-ring">
                <svg
                  viewBox="0 0 200 200"
                  role="img"
                  aria-label={`Capital engagé : ${investedPct != null ? fmtPctPoints(investedPct, 1, false) : '—'}`}
                >
                  <circle
                    cx="100"
                    cy="100"
                    r="80"
                    fill="none"
                    stroke="#eeeae3"
                    strokeWidth="19"
                  />
                  {investedPct != null && investedPct > 0 ? (
                    <circle
                      cx="100"
                      cy="100"
                      r="80"
                      pathLength="100"
                      fill="none"
                      stroke="#548f87"
                      strokeWidth="19"
                      strokeDasharray={`${investedPct} ${100 - investedPct}`}
                      strokeDashoffset={0}
                      transform="rotate(-90 100 100)"
                    />
                  ) : null}
                </svg>
                <div>
                  <b>{investedPct != null ? fmtPctPoints(investedPct, 1, false) : '—'}</b>
                  <small>Capital engagé</small>
                </div>
              </div>
              <div className="allocation-legend">
                <StatLine
                  label={
                    <>
                      <span className="legend-dot teal" />
                      Engagé
                    </>
                  }
                  value={acct ? fmtEur(acct.invested, 2) : '—'}
                />
                <StatLine
                  label={
                    <>
                      <span className="legend-dot neutral" />
                      Disponible
                    </>
                  }
                  value={acct ? fmtEur(acct.cash, 2) : '—'}
                />
                <p className="desk-note">
                  {acct && acct.equity > 0
                    ? `${fmtPct(acct.cash / acct.equity, 1, false)} du capital reste disponible.`
                    : '—'}
                </p>
              </div>
            </div>
            <div className="card-foot">
              <Link to="/app/portefeuille" className="link">
                Voir l’allocation ↗
              </Link>
            </div>
          </DeskCard>

          <DeskCard
            title="Concentration des positions"
            extra={
              concentration.length
                ? badge(concentrationLabel === '—' ? '—' : concentrationLabel, concentrationTone || 'gray')
                : badge('—', 'gray')
            }
          >
            <div className="allocation-body">
              <div className="desk-ring">
                <svg
                  viewBox="0 0 200 200"
                  role="img"
                  aria-label={`Positions ouvertes : ${concentration.length || '—'}`}
                >
                  <circle
                    cx="100"
                    cy="100"
                    r="80"
                    fill="none"
                    stroke="#eeeae3"
                    strokeWidth="19"
                  />
                  {concentration.slice(0, 3).map((c, i) => {
                    const o = concentration
                      .slice(0, i)
                      .reduce((s, x) => s + x.pct, 0)
                    const color = RING_COLORS[i % RING_COLORS.length]
                    return (
                      <circle
                        key={c.symbol}
                        cx="100"
                        cy="100"
                        r="80"
                        pathLength="100"
                        fill="none"
                        stroke={color}
                        strokeWidth="19"
                        strokeDasharray={`${c.pct} ${100 - c.pct}`}
                        strokeDashoffset={-o}
                        transform="rotate(-90 100 100)"
                      />
                    )
                  })}
                </svg>
                <div>
                  <b>{concentration.length ? String(Math.min(3, concentration.length)) : '—'}</b>
                  <small>Positions ouvertes</small>
                </div>
              </div>
              <div className="allocation-legend">
                {concentration.slice(0, 3).map((c, i) => (
                  <button
                    key={c.symbol}
                    type="button"
                    className="concentration-row"
                    onClick={() => openPosition(toEngineSymbol(c.symbol))}
                  >
                    <span>
                      <i style={{ background: RING_COLORS[i % RING_COLORS.length] }} />
                      {c.symbol}
                    </span>
                    <b className="mono">{fmtPctPoints(c.pct, 1, false)}</b>
                  </button>
                ))}
                <p className="desk-note">
                  {concentration.length ? '100 % de l’exposition en crypto spot.' : '—'}
                </p>
              </div>
            </div>
            <div className="card-foot">
              <Link to="/app/portefeuille" className="link">
                Surveiller la concentration ↗
              </Link>
            </div>
          </DeskCard>
        </div>
      </div>
    </div>
  )
}
