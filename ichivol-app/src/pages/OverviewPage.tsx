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
  formatVenueClock,
  nextHourlyClose,
  nextSessionOpen,
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
} from '../lib/paper'
import { getRiskLock, type RiskLockState } from '../lib/riskLock'
import { verdictBucket } from '../lib/deskSummarize'
import {
  DESK_PORTFOLIOS,
  type DeskPosition,
  concentrationBySymbol,
  deskPortfolio,
  drawdownOf,
  mergePositions,
  sumAccounts,
  sumCurves,
  sumRisk,
} from '../lib/deskPortfolios'
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
  portfolio: string
}

type DeskOrder = PaperOrderRow & { portfolio_code: string }

const MAX_EQUITY_MARKERS = 80

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

function nearKey(portfolio: string, symbol: string, ms: number): string {
  return `${portfolio}|${symbol.toUpperCase()}@${Math.round(ms / 120_000)}`
}

function buildEquityMarkers(
  actions: ActivityItem[],
  orders: DeskOrder[],
  period: EquityPeriod,
  now = Date.now(),
): EquityMarker[] {
  const cutoff = periodCutoffMs(period, now)
  const fromOrders: EquityMarker[] = []
  const covered = new Set<string>()

  for (const o of orders) {
    const ms = Date.parse(o.time)
    if (Number.isNaN(ms) || ms < cutoff) continue
    covered.add(nearKey(o.portfolio_code, o.symbol, ms))
    const side = String(o.side).toUpperCase()
    const isBuy = side === 'BUY'
    const notional =
      Number.isFinite(o.notional) && o.notional > 0 ? fmtEur(o.notional, 2) : '—'
    const px =
      Number.isFinite(o.filled_price) && o.filled_price > 0
        ? fmtPrice(o.filled_price)
        : '—'
    fromOrders.push({
      id: `tx-${o.portfolio_code}-${o.id}`,
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
      portfolio: o.portfolio_code,
    })
  }

  const fromActions: EquityMarker[] = []
  for (const it of actions) {
    const ms = Date.parse(it.time)
    if (Number.isNaN(ms) || ms < cutoff) continue
    const portfolio = it.portfolio || BASELINE
    if (covered.has(nearKey(portfolio, it.symbol, ms))) continue
    fromActions.push({
      id: `act-${portfolio}-${it.kind}-${it.symbol}-${it.time}`,
      ms,
      kind: it.kind,
      tone: it.tone,
      symbol: it.symbol,
      title: it.title,
      detail: it.detail || '—',
      source: 'action',
      portfolio,
    })
  }

  const merged = [...fromOrders, ...fromActions].sort((a, b) => a.ms - b.ms)
  if (merged.length <= MAX_EQUITY_MARKERS) return merged
  const rank = (m: EquityMarker): number => {
    if (m.source === 'transaction') return 3
    if (m.kind === 'paper_opened' || m.kind === 'paper_closed') return 2
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

/** Snapshots corrompus (79 M€…) — marche point à point autour de la médiane du compte. */
function cleanEquitySeries(
  points: { t: string; equity: number }[],
): { ms: number; equity: number }[] {
  const raw = points
    .map((p) => ({ ms: Date.parse(p.t), equity: p.equity }))
    .filter((p) => !Number.isNaN(p.ms) && Number.isFinite(p.equity) && p.equity > 0)
    .sort((a, b) => a.ms - b.ms)
  if (raw.length === 0) return []

  const sorted = [...raw.map((p) => p.equity)].sort((a, b) => a - b)
  const mid = sorted[Math.floor(sorted.length / 2)] ?? 5000
  const lo = mid * 0.9
  const hi = mid * 1.12

  const out: { ms: number; equity: number }[] = []
  for (const p of raw) {
    if (p.equity < lo || p.equity > hi) continue
    const prev = out[out.length - 1]
    if (prev) {
      if (p.ms === prev.ms) {
        out[out.length - 1] = p
        continue
      }
      const jump = Math.abs(p.equity - prev.equity)
      if (jump > Math.max(120, prev.equity * 0.04)) continue
    }
    out.push(p)
  }
  return out.length >= 2 ? out : raw.filter((p) => p.equity >= lo && p.equity <= hi)
}

/** Graduations type 4985 / 5010 / 5035 / 5060. */
function niceAxis(min: number, max: number): { min: number; max: number; ticks: number[] } {
  const span = Math.max(20, max - min)
  const pad = Math.max(8, span * 0.2)
  let lo = min - pad
  let hi = max + pad
  const step = span <= 90 ? 25 : span <= 200 ? 50 : 100
  lo = Math.floor(lo / step) * step
  hi = Math.ceil(hi / step) * step
  if (hi - lo < step * 3) {
    const mid = (lo + hi) / 2
    lo = Math.floor((mid - step * 1.5) / step) * step
    hi = lo + step * 3
  }
  const ticks: number[] = []
  for (let v = hi; v >= lo - 0.001; v -= step) ticks.push(v)
  return { min: lo, max: hi, ticks }
}

function fmtAxisNum(v: number): string {
  return Math.round(v).toLocaleString('fr-FR')
}

function fmtAxisTick(ms: number): string {
  return new Date(ms)
    .toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' })
    .replace(/\./g, '')
    .toUpperCase()
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

type EquitySeriesInput = {
  code: string
  label: string
  color: string
  points: { t: string; equity: number }[]
}

function EquityViz({
  series: inputs,
  period,
  actions,
  orders,
}: {
  series: EquitySeriesInput[]
  period: EquityPeriod
  actions: ActivityItem[]
  orders: DeskOrder[]
}) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const [activeId, setActiveId] = useState<string | null>(null)
  const [tipPos, setTipPos] = useState<{ left: number; top: number } | null>(null)

  const markers = useMemo(
    () => buildEquityMarkers(actions, orders, period),
    [actions, orders, period],
  )

  const w = 720
  const h = 248
  const padL = 14
  const padR = 48
  const padT = 14
  const padB = 34
  const innerW = w - padL - padR
  const innerH = h - padT - padB

  const lines = useMemo(
    () =>
      inputs
        .map((s) => ({ ...s, pts: cleanEquitySeries(filterEquityCurve(s.points, period)) }))
        .filter((s) => s.pts.length >= 2),
    [inputs, period],
  )

  const geometry = useMemo(() => {
    if (lines.length === 0) return null
    const vals = lines.flatMap((s) => s.pts.map((p) => p.equity))
    const { min, max, ticks: yTicks } = niceAxis(Math.min(...vals), Math.max(...vals))
    const span = Math.max(1e-6, max - min)
    const t0 = Math.min(...lines.map((s) => s.pts[0]!.ms))
    const t1 = Math.max(...lines.map((s) => s.pts[s.pts.length - 1]!.ms))
    const tSpan = Math.max(1, t1 - t0)
    const xAt = (ms: number) => padL + ((ms - t0) / tSpan) * innerW
    const yAt = (equity: number) => padT + (1 - (equity - min) / span) * innerH

    const paths = lines.map((s) => {
      const coords = s.pts.map((p) => [xAt(p.ms), yAt(p.equity)] as const)
      const d = coords.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(2)},${p[1].toFixed(2)}`).join(' ')
      return { code: s.code, label: s.label, color: s.color, d, last: coords[coords.length - 1]! }
    })

    const placed = markers
      .map((m) => {
        const line = lines.find((s) => s.code === m.portfolio) ?? lines[0]!
        if (m.ms < line.pts[0]!.ms - 60_000 || m.ms > line.pts[line.pts.length - 1]!.ms + 60_000) return null
        const eq = equityAtTime(line.pts, m.ms)
        if (eq == null) return null
        return { ...m, x: xAt(m.ms), y: yAt(eq), equity: eq, color: line.color, line: line.label }
      })
      .filter((m): m is NonNullable<typeof m> => m != null)
      .sort((a, b) => a.ms - b.ms)

    const xTicks = [t0, t0 + tSpan / 2, t1].map((ms) => ({ ms, x: xAt(ms) }))
    return { max, span, paths, placed, yTicks, xTicks }
  }, [lines, markers, innerW, innerH])

  const active = geometry?.placed.find((m) => m.id === activeId) ?? null

  const showTip = useCallback((id: string, clientX: number, clientY: number) => {
    const box = wrapRef.current?.getBoundingClientRect()
    if (!box) return
    setActiveId(id)
    const left = Math.min(Math.max(8, clientX - box.left + 12), box.width - 200)
    const top = Math.min(Math.max(8, clientY - box.top - 8), box.height - 12)
    setTipPos({ left, top })
  }, [])

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
        <p className="desk-eq-empty">Pas encore assez de points sur cette période.</p>
      </div>
    )
  }

  const { max, span, paths, placed, yTicks, xTicks } = geometry

  return (
    <div id="equity" className="desk-equity-wrap" ref={wrapRef}>
      <svg
        className="chart"
        viewBox={`0 0 ${w} ${h}`}
        role="img"
        aria-label={`Courbes des portefeuilles ${period} : ${paths.map((p) => p.label).join(', ')}`}
        onPointerLeave={hideTip}
      >
        {yTicks.map((v, i) => {
          const y = padT + ((max - v) / span) * innerH
          return (
            <g key={`y-${i}-${v}`}>
              <line x1={padL} y1={y} x2={w - padR} y2={y} stroke="#eeeae5" strokeDasharray="3 5" />
              <text
                x={w - padR + 6}
                y={y + 3}
                fontSize="10"
                fill="#939a9d"
                fontFamily="DM Mono, ui-monospace, monospace"
              >
                {fmtAxisNum(v)}
              </text>
            </g>
          )
        })}
        {paths.map((p) => (
          <path
            key={p.code}
            d={p.d}
            fill="none"
            stroke={p.color}
            strokeWidth="2"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        ))}
        {placed.map((m) => {
          const hot = activeId === m.id
          const isTx = m.source === 'transaction'
          return (
            <g key={m.id} className={`desk-eq-marker ${isTx ? 'is-tx' : markerToneClass(m.tone)}`}>
              <circle
                cx={m.x}
                cy={m.y}
                r={isTx ? (hot ? 6 : 4.5) : hot ? 5 : 3.5}
                fill={isTx ? '#fefdfb' : m.color}
                stroke={isTx ? m.color : '#fefdfb'}
                strokeWidth={isTx ? 1.7 : 1.2}
                role="button"
                tabIndex={0}
                aria-label={`${m.title} · ${m.line} · ${fmtMarkerWhen(m.ms)}`}
                onPointerEnter={(e) => showTip(m.id, e.clientX, e.clientY)}
                onBlur={hideTip}
                onClick={(e) => {
                  e.stopPropagation()
                  if (activeId === m.id) hideTip()
                  else showTip(m.id, e.clientX, e.clientY)
                }}
              />
            </g>
          )
        })}
        {paths.map((p) => (
          <circle key={`last-${p.code}`} cx={p.last[0]} cy={p.last[1]} r="4" fill={p.color} pointerEvents="none" />
        ))}
        {xTicks.map((tick, i) => (
          <text
            key={`x-${tick.ms}-${i}`}
            x={tick.x}
            y={h - 10}
            fontSize="10"
            fill="#969a9c"
            fontFamily="DM Mono, ui-monospace, monospace"
            textAnchor={i === 0 ? 'start' : i === xTicks.length - 1 ? 'end' : 'middle'}
          >
            {fmtAxisTick(tick.ms)}
          </text>
        ))}
      </svg>
      {active && tipPos ? (
        <div className="desk-eq-tip" role="tooltip" style={{ left: tipPos.left, top: tipPos.top }}>
          <header>
            <strong>{active.title}</strong>
            <span className={`desk-eq-tip-kind ${active.source}`}>
              {active.source === 'transaction' ? 'Transaction' : 'Action'}
            </span>
          </header>
          <p>{active.detail}</p>
          <dl>
            <div>
              <dt>Portefeuille</dt>
              <dd>{active.line}</dd>
            </div>
            <div>
              <dt>Quand</dt>
              <dd>{fmtMarkerWhen(active.ms)}</dd>
            </div>
            <div>
              <dt>Symbole</dt>
              <dd>{active.symbol || '—'}</dd>
            </div>
            <div>
              <dt>Valeur du portefeuille</dt>
              <dd>{fmtEur(active.equity, 2)}</dd>
            </div>
          </dl>
        </div>
      ) : null}
      {placed.length > 0 ? (
        <div className="desk-eq-legend" aria-hidden="true">
          <span>
            <i className="desk-eq-legend-dot is-tx" /> achat ou vente paper
          </span>
          <span>
            <i className="desk-eq-legend-dot is-action" /> autre action du circuit
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
  const [overviews, setOverviews] = useState<Record<string, PaperOverview | null>>({})
  const [tape, setTape] = useState<ActivityItem[]>([])
  const [equityActions, setEquityActions] = useState<ActivityItem[]>([])
  const [paperOrders, setPaperOrders] = useState<DeskOrder[]>([])
  const [locks, setLocks] = useState<Array<{ code: string; lock: RiskLockState | null }>>([])
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
    const [screenerRes, ovRes, feedRes, ordersRes, lockRes, healthRes, mktRes, fngRes, tickersRes] =
      await Promise.all([
        getScreener('1h', force)
          .then((r): ScreenerOk | Error => r)
          .catch((err: unknown): ScreenerOk | Error =>
            err instanceof Error ? err : new Error('Screener indisponible'),
          ),
        Promise.all(
          DESK_PORTFOLIOS.map((pf) =>
            getPaperOverview(pf.code)
              .then((r) => [pf.code, r] as const)
              .catch(() => [pf.code, null] as const),
          ),
        ),
        getActivityFeed(100)
          .then((r) => ({ ok: true as const, items: r.items }))
          .catch(() => ({ ok: false as const, items: [] as ActivityItem[] })),
        Promise.all(
          DESK_PORTFOLIOS.map((pf) =>
            getPaperActivity(pf.code, 200)
              .then((r): DeskOrder[] => r.map((o) => ({ ...o, portfolio_code: pf.code })))
              .catch((): DeskOrder[] => []),
          ),
        ).then((lists) => lists.flat()),
        Promise.all(
          DESK_PORTFOLIOS.map((pf) =>
            getRiskLock(pf.code)
              .then((lock) => ({ code: pf.code, lock }))
              .catch(() => ({ code: pf.code, lock: null })),
          ),
        ),
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

    setOverviews(Object.fromEntries(ovRes))

    if (feedRes.ok) {
      setEquityActions(feedRes.items)
      setTape(feedRes.items.slice(0, TAPE_LIMIT))
    } else {
      setEquityActions([])
      setTape([])
    }

    setPaperOrders(ordersRes)
    setLocks(lockRes)
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
  const overviewList = useMemo(
    () => DESK_PORTFOLIOS.map((pf) => ({ ...pf, overview: overviews[pf.code] ?? null })),
    [overviews],
  )
  const acct = useMemo(() => sumAccounts(overviewList.map((o) => o.overview)), [overviewList])
  const risk = useMemo(() => sumRisk(overviewList.map((o) => o.overview)), [overviewList])
  const positions = useMemo(() => mergePositions(overviewList), [overviewList])
  const equitySeries = useMemo(
    () =>
      overviewList
        .filter((o) => o.overview != null)
        .map((o) => ({ code: o.code, label: o.label, color: o.color, points: o.overview!.equity_curve ?? [] })),
    [overviewList],
  )
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

  const freshnessNotice = useMemo(() => {
    const stalePositions = positions.filter((p) => p.mark_stale)
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
  }, [rows, positions])

  const btcRow = rows.find((r) => r.symbol.toUpperCase() === 'BTCUSDT')
  const nextClose = nextHourlyClose(now)
  const selectedSession =
    MARKET_SESSIONS.find((s) => s.id === sessionId) ?? MARKET_SESSIONS[1]
  const selectedSt = sessionStatus(selectedSession, now)

  const investedPct =
    acct && acct.equity > 0 ? Math.min(100, Math.max(0, (acct.invested / acct.equity) * 100)) : null

  const concentration = useMemo(() => concentrationBySymbol(positions), [positions])

  const dd = useMemo(
    () => drawdownOf(sumCurves(equitySeries.map((s) => cleanEquitySeries(s.points)))),
    [equitySeries],
  )
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

  const knownLocks = locks.filter((l): l is { code: string; lock: RiskLockState } => l.lock != null)
  const blockedPortfolios = knownLocks
    .filter((l) => l.lock.entries_blocked || l.lock.daily_loss_locked || l.lock.kill_switch_armed)
    .map((l) => deskPortfolio(l.code)?.label ?? l.code)
  const riskPass = knownLocks.length === 0 ? null : blockedPortfolios.length === 0

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

  const openPosition = (symbol: string, portfolio?: string) => {
    const pf = portfolio && portfolio !== BASELINE ? `&pf=${encodeURIComponent(portfolio)}` : ''
    navigate(`/app/portefeuille?tab=positions${pf}&symbol=${encodeURIComponent(symbol)}`)
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
            <small>
              {acct
                ? `${acct.portfolios} portefeuille${acct.portfolios > 1 ? 's' : ''} paper additionnés · EUR`
                : 'Portefeuilles paper · EUR'}
            </small>
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
                CAPITAL TOTAL <b>{acct ? fmtEur(acct.equity, 2) : '—'}</b>
              </span>
              <span>
                RÉSULTAT DEPUIS LE DÉPART{' '}
                <b className={acct && acct.equity < acct.initial_cash ? 'down' : undefined}>
                  {acct ? fmtEur(acct.equity - acct.initial_cash, 2) : '—'}
                </b>
              </span>
              <span title="Baisse de la somme des trois portefeuilles depuis son plus haut.">
                DRAWDOWN DU TOTAL{' '}
                <b className={dd != null && dd < 0 ? 'down' : undefined}>
                  {dd != null ? fmtPct(dd, 1, true) : '—'}
                </b>
              </span>
            </div>
            <div className="desk-pf-legend">
              {overviewList.map((o) => {
                const a = o.overview?.account
                const ret = a && a.initial_cash > 0 ? a.equity / a.initial_cash - 1 : null
                return (
                  <span key={o.code} title={o.hint}>
                    <i style={{ background: o.color }} />
                    <b>{o.label}</b>
                    <span className="mono">{a ? fmtEur(a.equity, 2) : 'indisponible'}</span>
                    {ret != null ? (
                      <small className={ret > 0 ? 'up' : ret < 0 ? 'down' : undefined}>
                        {fmtPct(ret, 2, true)} depuis le départ
                      </small>
                    ) : null}
                  </span>
                )
              })}
            </div>
            <EquityViz
              series={equitySeries}
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
                  {positions.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="muted">
                        Aucune position ouverte dans les trois portefeuilles.
                      </td>
                    </tr>
                  ) : null}
                  {positions.slice(0, 6).map((p: DeskPosition) => {
                    const pf = deskPortfolio(p.portfolio_code)
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
                    const rule = p.portfolio_code === 'RS_D1_PAPER_V1' ? 'Donchian' : 'Ichimoku × RVOL'
                    const strat = [
                      pf?.label ?? p.portfolio_code,
                      p.timeframe != null ? `${rule} · ${String(p.timeframe).toUpperCase()}` : rule,
                    ].join(' · ')
                    return (
                      <tr
                        key={`${p.portfolio_code}-${p.id ?? p.symbol}`}
                        className="clickable"
                        tabIndex={0}
                        onClick={() => openPosition(p.symbol, p.portfolio_code)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            openPosition(p.symbol, p.portfolio_code)
                          }
                        }}
                      >
                        <td>
                          <b>
                            <i className="desk-pf-dot" style={{ background: pf?.color }} />
                            {base}
                          </b>
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
              <p className="desk-note" style={{ marginTop: 0 }}>
                {riskPass === false
                  ? `Nouvelles entrées bloquées sur : ${blockedPortfolios.join(', ')}.`
                  : 'Additionné sur les trois portefeuilles paper.'}
              </p>
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
                  ? `${fmtEur(acct.invested, 2)} engagés sur ${acct.open_positions} position${acct.open_positions > 1 ? 's' : ''}.`
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
                    ? '—'
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
                  {concentration.slice(0, RING_COLORS.length).map((c, i) => {
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
                  <b>{concentration.length ? String(concentration.length) : '—'}</b>
                  <small>{concentration.length > 1 ? 'Actifs exposés' : 'Actif exposé'}</small>
                </div>
              </div>
              <div className="allocation-legend">
                {concentration.slice(0, RING_COLORS.length).map((c, i) => (
                  <button
                    key={c.symbol}
                    type="button"
                    className="concentration-row"
                    onClick={() => {
                      const full = toEngineSymbol(c.symbol)
                      const at = positions.find((p) => p.symbol.toUpperCase() === full.toUpperCase())
                      openPosition(full, at?.portfolio_code)
                    }}
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
