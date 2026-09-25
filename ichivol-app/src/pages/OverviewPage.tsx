import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
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
  nextHourlyClose,
  type SessionId,
} from '../lib/marketSessions'
import {
  getPaperOverview,
  type PaperOverview,
} from '../lib/paper'
import { getRiskLock, type RiskLockState } from '../lib/riskLock'
import { verdictBucket } from '../lib/deskSummarize'
import { concentrationFromPositions } from '../components/desk/DeskRings'
import { AllocationSection } from './desk/AllocationSection'
import { EquitySection } from './desk/EquitySection'
import { EventsSection } from './desk/EventsSection'
import { KpiSection } from './desk/KpiSection'
import { SessionsSection } from './desk/SessionsSection'
import { WatchSection } from './desk/WatchSection'
import {
  BASELINE,
  PRIMARY_SYMBOLS,
  REFRESH_MS,
  TAPE_LIMIT,
  type EquityPeriod,
} from './desk/deskFormat'
import './OverviewPage.css'

function pickPrimaryMarkets(rows: ScreenerDecisionRow[]): ScreenerDecisionRow[] {
  const bySym = new Map(rows.map((r) => [r.symbol.toUpperCase(), r]))
  const preferred = PRIMARY_SYMBOLS.map((s) => bySym.get(s)).filter(
    (r): r is ScreenerDecisionRow => Boolean(r),
  )
  if (preferred.length >= 4) return preferred.slice(0, 6)
  const rest = [...rows]
    .filter((r) => !PRIMARY_SYMBOLS.includes(r.symbol.toUpperCase()))
    .sort((a, b) => b.confidence - a.confidence)
  return [...preferred, ...rest].slice(0, 6)
}

export function OverviewPage() {
  const [rows, setRows] = useState<ScreenerDecisionRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [overview, setOverview] = useState<PaperOverview | null>(null)
  const [ovError, setOvError] = useState<string | null>(null)
  const [tape, setTape] = useState<ActivityItem[]>([])
  const [tapeError, setTapeError] = useState<string | null>(null)
  const [lock, setLock] = useState<RiskLockState | null>(null)
  const [engineOk, setEngineOk] = useState<boolean | null>(null)
  const [market, setMarket] = useState<GlobalMarketData | null>(null)
  const [fng, setFng] = useState<FearGreed | null>(null)
  const [climateError, setClimateError] = useState<string | null>(null)
  const [changeBySymbol, setChangeBySymbol] = useState<Record<string, number>>({})
  const [sessionId, setSessionId] = useState<SessionId>('london')
  const [equityPeriod, setEquityPeriod] = useState<EquityPeriod>('1M')
  const [nowTick, setNowTick] = useState(() => Date.now())

  const load = useCallback(async (force = false) => {
    setLoading(true)
    type ScreenerOk = Awaited<ReturnType<typeof getScreener>>
    const [screenerRes, ovRes, feedRes, lockRes, healthRes, mktRes, fngRes, tickersRes] =
      await Promise.all([
      getScreener('1h', force)
        .then((r): ScreenerOk | Error => r)
        .catch((err: unknown): ScreenerOk | Error =>
          err instanceof Error ? err : new Error('Screener indisponible'),
        ),
      getPaperOverview(BASELINE)
        .then((r) => ({ ok: true as const, data: r }))
        .catch((err: unknown) => ({
          ok: false as const,
          error: err instanceof Error ? err.message : 'Overview indisponible',
        })),
      getActivityFeed(40)
        .then((r) => ({ ok: true as const, items: r.items }))
        .catch((err: unknown) => ({
          ok: false as const,
          error: err instanceof Error ? err.message : 'Feed indisponible',
          items: [] as ActivityItem[],
        })),
      getRiskLock(BASELINE).catch(() => null),
      fetch('/api/engine/health', { credentials: 'include' })
        .then(async (res) => {
          if (!res.ok) return { engine: false }
          const j = (await res.json().catch(() => null)) as { status?: string; ok?: boolean } | null
          const ok = j?.ok === true || j?.status === 'ok' || j?.status === 'healthy'
          return { engine: Boolean(ok) }
        })
        .catch(() => ({ engine: false })),
      fetchGlobalMarket()
        .then((m) => ({ ok: true as const, data: m }))
        .catch((err: unknown) => ({
          ok: false as const,
          error: err instanceof Error ? err.message : 'CoinGecko indisponible',
        })),
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
      const msg = screenerRes.message
      setError(
        msg.includes('engine_unreachable') || msg.includes('502')
          ? 'Moteur Python injoignable — lance l’engine pour le desk.'
          : msg,
      )
      setRows([])
    } else {
      setError(null)
      setRows(screenerRes.rows)
    }

    if (ovRes.ok) {
      setOverview(ovRes.data)
      setOvError(null)
    } else {
      setOverview(null)
      setOvError(ovRes.error)
    }

    if (feedRes.ok) {
      setTape(feedRes.items.slice(0, TAPE_LIMIT))
      setTapeError(null)
    } else {
      setTape([])
      setTapeError(feedRes.error)
    }

    setLock(lockRes)
    setEngineOk(healthRes.engine)

    if (mktRes.ok) {
      setMarket(mktRes.data)
      setClimateError(null)
    } else {
      setMarket(null)
      setClimateError(mktRes.error)
    }
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
  const dayTone: 'bull' | 'bear' | 'flat' =
    acct?.day_change == null ? 'flat' : acct.day_change > 0 ? 'bull' : acct.day_change < 0 ? 'bear' : 'flat'
  const dayPct =
    acct?.day_change != null && acct.equity
      ? acct.day_change / Math.max(1e-9, acct.equity - acct.day_change)
      : null

  const watchList = useMemo(() => {
    return rows
      .filter((r) => {
        const b = verdictBucket(r)
        return b === 'buy' || b === 'sell'
      })
      .sort((a, b) => b.confidence - a.confidence)
      .slice(0, 6)
  }, [rows])

  const primaryMarkets = useMemo(() => pickPrimaryMarkets(rows), [rows])

  const freshnessIssues = useMemo(() => {
    const staleSyms = rows
      .filter((r) => r.data_quality?.stale || r.data_quality?.data_late)
      .map((r) => r.symbol.replace(/USDT$/i, ''))
    const markStale = (overview?.positions ?? [])
      .filter((p) => p.mark_stale)
      .map((p) => p.symbol.replace(/USDT$/i, ''))
    const uniq = [...new Set([...staleSyms, ...markStale])]
    return uniq
  }, [rows, overview?.positions])

  const btcRow = rows.find((r) => r.symbol.toUpperCase() === 'BTCUSDT')
  const nextClose = nextHourlyClose(now)

  const selectedSession =
    MARKET_SESSIONS.find((s) => s.id === sessionId) ?? MARKET_SESSIONS[1]

  const investedPct =
    acct && acct.equity > 0 ? Math.min(100, Math.max(0, (acct.invested / acct.equity) * 100)) : 0

  const concentration = useMemo(
    () => concentrationFromPositions(overview?.positions ?? []),
    [overview?.positions],
  )

  return (
    <div className="overview-page desk-workspace">
      <header className="iv-page-header page-head overview-head iv-animate-soft">
        <div>
          <p className="iv-page-eyebrow">Trading · Desk</p>
          <h1>Desk</h1>
          <p className="iv-page-question">Votre marché, en un regard.</p>
        </div>
        <div className="page-head-actions">
          <button type="button" className="ghost" onClick={() => void load(true)} disabled={loading}>
            {loading ? 'Actualisation…' : 'Actualiser'}
          </button>
          <Link to="/app/market" className="link">
            Ouvrir le marché ↗
          </Link>
        </div>
      </header>

      {error && (
        <div className="banner error" role="alert">
          {error}
        </div>
      )}

      <KpiSection
        loading={loading}
        acct={acct}
        risk={risk}
        dayTone={dayTone}
        dayPct={dayPct}
        ovError={ovError}
      />

      <SessionsSection
        now={now}
        sessionId={sessionId}
        setSessionId={setSessionId}
        selectedSession={selectedSession}
        loading={loading}
        primaryMarkets={primaryMarkets}
        changeBySymbol={changeBySymbol}
        climateError={climateError}
        market={market}
        fng={fng}
      />

      <EquitySection
        ovError={ovError}
        points={overview?.equity_curve ?? []}
        initial={acct?.initial_cash ?? 0}
        period={equityPeriod}
        onPeriod={setEquityPeriod}
      />

      <WatchSection
        loading={loading}
        watchList={watchList}
        freshnessIssues={freshnessIssues}
        ovError={ovError}
        overview={overview}
        acct={acct}
        risk={risk}
        lock={lock}
      />

      <EventsSection
        tape={tape}
        tapeError={tapeError}
        nextClose={nextClose}
        now={now}
        btcRow={btcRow}
        loading={loading}
        engineOk={engineOk}
        risk={risk}
        lock={lock}
      />

      <AllocationSection
        loading={loading}
        ovError={ovError}
        acct={acct}
        investedPct={investedPct}
        concentration={concentration}
      />
    </div>
  )
}
