/**
 * Desk — port littéral de design-reference/ichivol-workspace `desk()` + page-head.
 * Classes HTML = maquette. Données = engine (pas de démo inventée ; manquant → « — »).
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
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
  nextHourlyClose,
  sessionStatus,
  sessionStatusLabel,
  type SessionId,
  type SessionStatus,
} from '../lib/marketSessions'
import {
  getPaperActivity,
  getPaperOverview,
  type PaperOrderRow,
  type PaperOverview,
  type PaperOverviewPosition,
} from '../lib/paper'
import { getRiskLock, type RiskLockState } from '../lib/riskLock'
import { verdictBucket } from '../lib/deskSummarize'
import { concentrationFromPositions } from '../components/desk/deskMetrics'
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

function periodCutoffMs(period: EquityPeriod, now = Date.now()): number {
  const ms =
    period === '1J'
      ? 86_400_000
      : period === '1S'
        ? 7 * 86_400_000
        : period === '1M'
          ? 30 * 86_400_000
          : 90 * 86_400_000
  return now - ms
}

function filterEquityCurve(
  points: { t: string; equity: number }[],
  period: EquityPeriod,
  now = Date.now(),
): { t: string; equity: number }[] {
  const cutoff = periodCutoffMs(period, now)
  return points.filter((p) => {
    const t = Date.parse(p.t)
    return !Number.isNaN(t) && t >= cutoff
  })
}

type EquityMarkerKind =
  | 'tx_buy'
  | 'tx_sell'
  | 'paper_opened'
  | 'paper_closed'
  | 'shadow_blocked'
  | 'shadow_closed'

type EquityMarker = {
  id: string
  ms: number
  kind: EquityMarkerKind
  tone: FeedTone
  symbol: string
  title: string
  detail: string
  source: 'transaction' | 'action'
}

const MAX_EQUITY_MARKERS = 48

function equityAtTime(
  series: { ms: number; equity: number }[],
  ms: number,
): number | null {
  if (series.length === 0) return null
  if (ms <= series[0]!.ms) return series[0]!.equity
  const last = series[series.length - 1]!
  if (ms >= last.ms) return last.equity
  for (let i = 1; i < series.length; i++) {
    const b = series[i]!
    if (ms <= b.ms) {
      const a = series[i - 1]!
      const r = (ms - a.ms) / Math.max(1, b.ms - a.ms)
      return a.equity + r * (b.equity - a.equity)
    }
  }
  return null
}

function nearKey(symbol: string, ms: number): string {
  return `${symbol.toUpperCase()}@${Math.round(ms / 120_000)}`
}

function buildEquityMarkers(
  actions: ActivityItem[],
  orders: PaperOrderRow[],
  period: EquityPeriod,
  now = Date.now(),
): EquityMarker[] {
  const cutoff = periodCutoffMs(period, now)
  const fromActions: EquityMarker[] = []
  const covered = new Set<string>()

  for (const it of actions) {
    const ms = Date.parse(it.time)
    if (Number.isNaN(ms) || ms < cutoff) continue
    covered.add(nearKey(it.symbol, ms))
    fromActions.push({
      id: `act-${it.kind}-${it.symbol}-${it.time}`,
      ms,
      kind: it.kind,
      tone: it.tone,
      symbol: it.symbol,
      title: it.title,
      detail: it.detail || '—',
      source: 'action',
    })
  }

  const fromOrders: EquityMarker[] = []
  for (const o of orders) {
    const ms = Date.parse(o.time)
    if (Number.isNaN(ms) || ms < cutoff) continue
    if (covered.has(nearKey(o.symbol, ms))) continue
    const side = String(o.side).toUpperCase()
    const isBuy = side === 'BUY'
    const notional =
      Number.isFinite(o.notional) && o.notional > 0
        ? fmtEur(o.notional, 2)
        : '—'
    const px =
      Number.isFinite(o.filled_price) && o.filled_price > 0
        ? fmtPrice(o.filled_price)
        : '—'
    fromOrders.push({
      id: `tx-${o.id}`,
      ms,
      kind: isBuy ? 'tx_buy' : 'tx_sell',
      tone: isBuy ? 'good' : 'neutral',
      symbol: o.symbol,
      title: `${isBuy ? 'Achat' : 'Vente'} ${o.symbol}`,
      detail: [
        `${side} · ${fmtDec(o.qty, 4)} @ ${px}`,
        `notional ${notional}`,
        o.reason?.trim() || null,
        o.status ? `statut ${o.status}` : null,
      ]
        .filter(Boolean)
        .join(' · '),
      source: 'transaction',
    })
  }

  const merged = [...fromActions, ...fromOrders].sort((a, b) => a.ms - b.ms)
  if (merged.length <= MAX_EQUITY_MARKERS) return merged
  // Prefer opens/closes + recent txs when dense.
  const rank = (m: EquityMarker): number => {
    if (m.kind === 'paper_opened' || m.kind === 'paper_closed') return 3
    if (m.kind === 'tx_buy' || m.kind === 'tx_sell') return 2
    return 1
  }
  return [...merged]
    .sort((a, b) => rank(b) - rank(a) || b.ms - a.ms)
    .slice(0, MAX_EQUITY_MARKERS)
    .sort((a, b) => a.ms - b.ms)
}

function markerToneClass(tone: FeedTone): string {
  switch (tone) {
    case 'good':
      return 'is-good'
    case 'bad':
      return 'is-bad'
    case 'blocked':
      return 'is-blocked'
    case 'neutral':
      return 'is-neutral'
    default: {
      const _exhaustive: never = tone
      return _exhaustive
    }
  }
}

function fmtMarkerWhen(ms: number): string {
  return new Date(ms).toLocaleString('fr-FR', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

function drawdownRatio(
  curve: { equity: number }[],
  equity: number | null | undefined,
): number | null {
  if (equity == null || !Number.isFinite(equity) || curve.length === 0) return null
  let peak = equity
  for (const p of curve) {
    if (Number.isFinite(p.equity) && p.equity > peak) peak = p.equity
  }
  if (peak <= 0) return null
  return (equity - peak) / peak
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

function EquityViz({
  points,
  period,
  actions,
  orders,
}: {
  points: { t: string; equity: number }[]
  period: EquityPeriod
  actions: ActivityItem[]
  orders: PaperOrderRow[]
}) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const [activeId, setActiveId] = useState<string | null>(null)
  const [tipPos, setTipPos] = useState<{ left: number; top: number } | null>(null)

  const filtered = useMemo(() => filterEquityCurve(points, period), [points, period])
  const markers = useMemo(
    () => buildEquityMarkers(actions, orders, period),
    [actions, orders, period],
  )

  const w = 720
  const h = 230
  const padL = 25
  const padR = 46
  const padT = 20
  const padB = 30
  const innerW = w - padL - padR
  const innerH = h - padT - padB

  const series = useMemo(
    () =>
      filtered
        .map((p) => ({ ms: Date.parse(p.t), equity: p.equity }))
        .filter((p) => !Number.isNaN(p.ms)),
    [filtered],
  )

  const geometry = useMemo(() => {
    if (series.length < 2) return null
    const vals = series.map((p) => p.equity)
    const min = Math.min(...vals)
    const max = Math.max(...vals)
    const span = Math.max(1e-6, max - min)
    const t0 = series[0]!.ms
    const t1 = series[series.length - 1]!.ms
    const tSpan = Math.max(1, t1 - t0)
    const xAt = (ms: number) => padL + ((ms - t0) / tSpan) * innerW
    const yAt = (equity: number) => padT + (1 - (equity - min) / span) * innerH
    const coords = series.map((p) => [xAt(p.ms), yAt(p.equity)] as const)
    const d = coords.map((p, i) => `${i ? 'L' : 'M'}${p[0]},${p[1]}`).join(' ')
    const last = coords[coords.length - 1]!
    const area = `${d} L${last[0]},${h - padB} L${padL},${h - padB}Z`
    const placed = markers
      .map((m) => {
        const eq = equityAtTime(series, m.ms)
        if (eq == null) return null
        return { ...m, x: xAt(m.ms), y: yAt(eq), equity: eq }
      })
      .filter((m): m is EquityMarker & { x: number; y: number; equity: number } => m != null)
    return { min, max, span, d, area, last, placed, vals }
  }, [series, markers, innerW, innerH])

  const active = geometry?.placed.find((m) => m.id === activeId) ?? null

  const showTip = useCallback(
    (id: string, clientX: number, clientY: number) => {
      const box = wrapRef.current?.getBoundingClientRect()
      if (!box) return
      setActiveId(id)
      const left = Math.min(Math.max(8, clientX - box.left + 12), box.width - 200)
      const top = Math.min(Math.max(8, clientY - box.top - 8), box.height - 12)
      setTipPos({ left, top })
    },
    [],
  )

  const hideTip = useCallback(() => {
    setActiveId(null)
    setTipPos(null)
  }, [])

  useEffect(() => {
    hideTip()
  }, [period, hideTip])

  if (!geometry) {
    return (
      <div id="equity" className="desk-equity-wrap" ref={wrapRef}>
        <svg
          className="chart"
          viewBox={`0 0 ${w} ${h}`}
          role="img"
          aria-label="Courbe de performance indisponible"
        />
      </div>
    )
  }

  const { max, span, d, area, last, placed } = geometry
  const labels = [filtered[0], filtered[Math.floor(filtered.length / 2)], filtered[filtered.length - 1]]
    .filter(Boolean)
    .map((p) => {
      const t = Date.parse(p.t)
      if (Number.isNaN(t)) return '—'
      return new Date(t)
        .toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' })
        .toUpperCase()
    })

  return (
    <div id="equity" className="desk-equity-wrap" ref={wrapRef}>
      <svg
        className="chart"
        viewBox={`0 0 ${w} ${h}`}
        role="img"
        aria-label={`Courbe equity ${period}${placed.length ? ` · ${placed.length} événements` : ''}`}
        onPointerLeave={hideTip}
      >
        <defs>
          <linearGradient id="desk-eq-fade" x1="0" y1="0" x2="0" y2="1">
            <stop stopColor="#b5d6cc" stopOpacity=".35" />
            <stop offset="1" stopColor="#b5d6cc" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0, 1, 2, 3].map((i) => {
          const y = padT + (i / 3) * innerH
          const v = max - (i / 3) * span
          return (
            <g key={i}>
              <line x1={padL} y1={y} x2={w - padR} y2={y} stroke="#eeeae5" strokeDasharray="3 5" />
              <text x={w - padR + 4} y={y + 3} fontSize="9" fill="#939a9d">
                {Math.round(v)}
              </text>
            </g>
          )
        })}
        <path d={area} fill="url(#desk-eq-fade)" />
        <path d={d} fill="none" stroke="#478f83" strokeWidth="2" />
        {placed.map((m) => (
          <g key={m.id} className={`desk-eq-marker ${markerToneClass(m.tone)}`}>
            <circle
              cx={m.x}
              cy={m.y}
              r={activeId === m.id ? 6 : 4.5}
              className="desk-eq-marker-dot"
              role="button"
              tabIndex={0}
              aria-label={`${m.title} · ${fmtMarkerWhen(m.ms)}`}
              onPointerEnter={(e) => showTip(m.id, e.clientX, e.clientY)}
              onFocus={(e) => {
                const box = wrapRef.current?.getBoundingClientRect()
                const svg = (e.target as SVGCircleElement).ownerSVGElement
                if (!box || !svg) return
                const pt = svg.createSVGPoint()
                pt.x = m.x
                pt.y = m.y
                const ctm = svg.getScreenCTM()
                if (!ctm) return
                const screen = pt.matrixTransform(ctm)
                showTip(m.id, screen.x, screen.y)
              }}
              onBlur={hideTip}
              onClick={(e) => {
                e.stopPropagation()
                if (activeId === m.id) hideTip()
                else showTip(m.id, e.clientX, e.clientY)
              }}
            />
            {m.source === 'transaction' ? (
              <circle
                cx={m.x}
                cy={m.y}
                r={2}
                className="desk-eq-marker-core"
                pointerEvents="none"
              />
            ) : null}
          </g>
        ))}
        <circle cx={last[0]} cy={last[1]} r="4" fill="#478f83" pointerEvents="none" />
      </svg>
      {active && tipPos ? (
        <div
          className="desk-eq-tip"
          role="tooltip"
          style={{ left: tipPos.left, top: tipPos.top }}
        >
          <header>
            <strong>{active.title}</strong>
            <span className={`desk-eq-tip-kind ${active.source}`}>
              {active.source === 'transaction' ? 'Transaction' : 'Action'}
            </span>
          </header>
          <p>{active.detail}</p>
          <dl>
            <div>
              <dt>Quand</dt>
              <dd>{fmtMarkerWhen(active.ms)}</dd>
            </div>
            <div>
              <dt>Symbole</dt>
              <dd>{active.symbol || '—'}</dd>
            </div>
            <div>
              <dt>Equity</dt>
              <dd>{fmtEur(active.equity, 2)}</dd>
            </div>
          </dl>
        </div>
      ) : null}
      <div className="chart-labels">
        {labels.map((l, i) => (
          <span key={`${l}-${i}`}>{l}</span>
        ))}
      </div>
      {placed.length > 0 ? (
        <div className="desk-eq-legend" aria-hidden="true">
          <span>
            <i className="desk-eq-legend-dot is-tx" /> transactions paper
          </span>
          <span>
            <i className="desk-eq-legend-dot is-action" /> actions circuit
          </span>
        </div>
      ) : null}
    </div>
  )
}

export function OverviewPage() {
  const navigate = useNavigate()
  const [rows, setRows] = useState<ScreenerDecisionRow[]>([])
  const [loading, setLoading] = useState(true)
  const [overview, setOverview] = useState<PaperOverview | null>(null)
  const [tape, setTape] = useState<ActivityItem[]>([])
  const [equityActions, setEquityActions] = useState<ActivityItem[]>([])
  const [paperOrders, setPaperOrders] = useState<PaperOrderRow[]>([])
  const [lock, setLock] = useState<RiskLockState | null>(null)
  const [engineOk, setEngineOk] = useState<boolean | null>(null)
  const [market, setMarket] = useState<GlobalMarketData | null>(null)
  const [fng, setFng] = useState<FearGreed | null>(null)
  const [changeBySymbol, setChangeBySymbol] = useState<Record<string, number>>({})
  const [sessionId, setSessionId] = useState<SessionId>('london')
  const [equityPeriod, setEquityPeriod] = useState<EquityPeriod>('1M')
  const [nowTick, setNowTick] = useState(() => Date.now())

  const load = useCallback(async (force = false) => {
    setLoading(true)
    type ScreenerOk = Awaited<ReturnType<typeof getScreener>>
    const [screenerRes, ovRes, feedRes, ordersRes, lockRes, healthRes, mktRes, fngRes, tickersRes] =
      await Promise.all([
        getScreener('1h', force)
          .then((r): ScreenerOk | Error => r)
          .catch((err: unknown): ScreenerOk | Error =>
            err instanceof Error ? err : new Error('Screener indisponible'),
          ),
        getPaperOverview(BASELINE)
          .then((r) => ({ ok: true as const, data: r }))
          .catch(() => ({ ok: false as const })),
        getActivityFeed(100)
          .then((r) => ({ ok: true as const, items: r.items }))
          .catch(() => ({ ok: false as const, items: [] as ActivityItem[] })),
        getPaperActivity(BASELINE, 120)
          .then((r) => ({ ok: true as const, orders: r }))
          .catch(() => ({ ok: false as const, orders: [] as PaperOrderRow[] })),
        getRiskLock(BASELINE).catch(() => null),
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
      setEquityActions(feedRes.items)
      setTape(feedRes.items.slice(0, TAPE_LIMIT))
    } else {
      setEquityActions([])
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
  const dayUp = (acct?.day_change ?? 0) > 0
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
      .slice(0, 3)
  }, [rows])

  const primaryMarkets = useMemo(() => pickPrimaryMarkets(rows), [rows])

  const freshnessIssues = useMemo(() => {
    const staleSyms = rows
      .filter((r) => r.data_quality?.stale || r.data_quality?.data_late)
      .map((r) => r.symbol.replace(/USDT$/i, ''))
    const markStale = (overview?.positions ?? [])
      .filter((p) => p.mark_stale)
      .map((p) => p.symbol.replace(/USDT$/i, ''))
    return [...new Set([...staleSyms, ...markStale])]
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
  const climateTitle = fng?.classification ?? '—'

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
    const full = /USDT$/i.test(symbol) ? symbol.toUpperCase() : `${symbol.toUpperCase()}USDT`
    navigate(`/app/market?symbol=${encodeURIComponent(full)}`)
  }

  const openOpp = (symbol: string) => {
    const full = /USDT$/i.test(symbol) ? symbol.toUpperCase() : `${symbol.toUpperCase()}USDT`
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
          <p className="subtitle">Votre marché, en un regard.</p>
        </div>
        <div className="actions">
          <span className="subtitle">{loading && !acct ? '—' : dateLabel || '—'}</span>
          <Link className="link" to="/app/market" style={{ marginLeft: 14 }}>
            Ouvrir le marché ↗
          </Link>
        </div>
      </div>

      <div className="desk-workspace">
        <div className="metrics">
          <div className="metric featured">
            <div className="metric-label">
              Capital total<span>↗</span>
            </div>
            <div className="metric-value">{acct ? fmtEur(acct.equity, 2) : '—'}</div>
            <small>Portefeuille paper · EUR</small>
          </div>
          <div className="metric">
            <div className="metric-label">
              Disponible<span>↗</span>
            </div>
            <div className="metric-value">{acct ? fmtEur(acct.cash, 2) : '—'}</div>
            <small>
              {acct && acct.equity > 0
                ? `${fmtPct(acct.cash / acct.equity, 1, false)} du capital`
                : '—'}
            </small>
          </div>
          <div className={`metric${dayUp ? ' up' : ''}`.trim()}>
            <div className="metric-label">
              P&amp;L du jour<span>↗</span>
            </div>
            <div className="metric-value">
              {acct?.day_change != null ? fmtEur(acct.day_change, 2) : '—'}
            </div>
            <small>
              {dayPct != null ? `↗ ${fmtPct(dayPct)} aujourd’hui` : '—'}
            </small>
          </div>
          <div className="metric">
            <div className="metric-label">
              Risque utilisé<span>↗</span>
            </div>
            <div className="metric-value">
              {risk?.open_risk_pct != null
                ? fmtPct(risk.open_risk_pct, 1, false)
                : '—'}
            </div>
            <small>
              {risk?.max_open_risk_pct != null
                ? `Limite de risque ouverte : ${fmtPct(risk.max_open_risk_pct, 0, false)}`
                : '—'}
            </small>
          </div>
        </div>

        <div className="desk-overview">
          <DeskCard title="Sessions de marché" extra={badge('APERÇU', 'gray')} className="world-card">
            <div className="world-view">
              <img
                src="/world-map.svg"
                alt="Carte du monde situant les sessions de Londres, New York et Tokyo"
                width={720}
                height={290}
              />
              {MARKET_SESSIONS.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  className={`map-marker${sessionId === s.id ? ' selected' : ''}`}
                  style={{ left: `${s.mapLeftPct}%`, top: `${s.mapTopPct}%` }}
                  aria-label={`Session ${s.city}`}
                  aria-pressed={sessionId === s.id}
                  onClick={() => setSessionId(s.id)}
                >
                  <span />
                  <b>{s.city}</b>
                </button>
              ))}
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
                    <small>{sessionStatusLabel(st)}</small>
                  </button>
                )
              })}
            </div>
            <div id="desk-session-detail" className="session-detail">
              <strong>
                {selectedSession.city}{' '}
                <span className={sessionStatusClass(selectedSt)}>
                  {sessionStatusLabel(selectedSt)}
                </span>
              </strong>
              <span className="mono">{formatSessionHoursUtc(selectedSession, now)}</span>
            </div>
            <div className="map-foot">
              Sessions illustratives · horaires de l’aperçu{' '}
              <span>
                Crypto <b>24/7</b>
              </span>
            </div>
          </DeskCard>

          <DeskCard title="Marchés principaux" extra={badge(rows.length ? 'LIVE' : '—', 'gray')}>
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
                      <small>{r.decision ? String(r.decision) : '—'}</small>
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
                  <small>RÉGIME DE L’APERÇU</small>
                  <h3>{climateTitle}</h3>
                </div>
              </div>
              <StatLine label="Volatilité" value="—" />
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
            title="Trajectoire du portefeuille"
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
                CAPITAL <b>{acct ? fmtEur(acct.equity, 2) : '—'}</b>
              </span>
              <span>
                DRAWDOWN{' '}
                <b className={dd != null && dd < 0 ? 'down' : undefined}>
                  {dd != null ? fmtPct(dd, 1, true) : '—'}
                </b>
              </span>
            </div>
            <EquityViz
              points={overview?.equity_curve ?? []}
              period={equityPeriod}
              actions={equityActions}
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

        <div className="notice">
          <span>△</span>
          <span>
            <b>Une donnée demande votre attention.</b>{' '}
            {freshnessIssues.length > 0
              ? `${freshnessIssues.slice(0, 4).join(', ')}${
                  freshnessIssues.length > 4 ? ` (+${freshnessIssues.length - 4})` : ''
                } : fraîcheur ou mark périmé.`
              : '—'}
          </span>
          <Link to="/app/operations">Vérifier →</Link>
        </div>

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
                  {(overview?.positions ?? []).slice(0, 3).map((p: PaperOverviewPosition) => {
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
                        ? `Ichimoku × RVOL · ${String(p.timeframe).toUpperCase()}`
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
                    onClick={() => openPosition(`${c.symbol}USDT`)}
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
