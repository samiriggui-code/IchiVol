import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import {
  getActivityFeed,
  getActivitySummary,
  type ActivityItem,
  type ActivitySummary,
} from '../lib/activity'
import {
  getBacktestEvidence,
  type BacktestEvidenceSummary,
} from '../lib/backtest'
import {
  getScreener,
  type DecisionLabel,
  type ScreenerDecisionRow,
} from '../lib/decisions'
import {
  getPaperOverview,
  listPaperPortfolios,
  type PaperOverview,
  type PaperOverviewPosition,
  type PaperPortfolioRow,
} from '../lib/paper'
import { asGate } from '../lib/verdict'
import { workspaceEyebrow } from '../lib/workspaceNav'

const BASELINE = 'ICHIVOL_BASELINE_V1'
const REFRESH_MS = 60_000
const TAPE_LIMIT = 8

const DESK_SESSIONS = [
  { region: 'Asie', city: 'Tokyo', status: 'Clôturée', hours: '00:00–09:00 UTC', left: 77.6, top: 34.6 },
  { region: 'Europe', city: 'Londres', status: 'Ouverte', hours: '07:00–16:00 UTC', left: 50, top: 23.1 },
  { region: 'États-Unis', city: 'New York', status: 'À venir', hours: '13:30–20:00 UTC', left: 29.4, top: 30.6 },
] as const

const PERIODS = ['1J', '1S', '1M', '3M'] as const
type Period = (typeof PERIODS)[number]

const RING_COLORS = ['#548f87', '#8c9eb4', '#c2b596', '#a8b5a0'] as const

function fmtCacheAge(seconds: number): string {
  if (seconds < 5) return 'à l’instant'
  if (seconds < 60) return `il y a ${Math.floor(seconds)}s`
  return `il y a ${Math.floor(seconds / 60)} min`
}

function isBuy(d: DecisionLabel): boolean {
  return d === 'BUY' || d === 'STRONG_BUY'
}

function isSell(d: DecisionLabel): boolean {
  return d === 'SELL' || d === 'STRONG_SELL'
}

function isWatch(d: DecisionLabel): boolean {
  return d === 'WATCH' || d === 'WAIT'
}

function verdictBucket(r: ScreenerDecisionRow): 'buy' | 'sell' | 'watch' | 'none' {
  const gate = asGate(r.pipeline?.decision as string | undefined)
  if (gate) {
    if (gate === 'BUY') return 'buy'
    if (gate === 'SELL') return 'sell'
    if (gate === 'WATCH') return 'watch'
    return 'none'
  }
  if (isBuy(r.decision)) return 'buy'
  if (isSell(r.decision)) return 'sell'
  if (isWatch(r.decision)) return 'watch'
  return 'none'
}

function summarize(rows: ScreenerDecisionRow[]) {
  let buy = 0
  let sell = 0
  let watch = 0
  for (const r of rows) {
    const bucket = verdictBucket(r)
    if (bucket === 'buy') buy += 1
    else if (bucket === 'sell') sell += 1
    else if (bucket === 'watch') watch += 1
  }
  const top = rows
    .filter((r) => {
      const b = verdictBucket(r)
      return b === 'buy' || b === 'sell'
    })
    .sort((a, b) => b.confidence - a.confidence)
    .slice(0, 6)
  return { buy, sell, watch, top, total: rows.length }
}

function fmtPct(v: number | null | undefined, digits = 1): string {
  if (v == null || Number.isNaN(v)) return '—'
  const sign = v > 0 ? '+' : ''
  return `${sign}${(v * 100).toFixed(digits)} %`
}

function fmtEur(v: number | null | undefined, digits = 2): string {
  if (v == null || Number.isNaN(v)) return '—'
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(v)
}

function fmtPrice(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '—'
  return new Intl.NumberFormat('fr-FR', {
    maximumFractionDigits: v >= 100 ? 2 : 4,
    minimumFractionDigits: 2,
  }).format(v)
}

function fmtClock(iso: string): string {
  return new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
}

function displaySymbol(symbol: string): string {
  return symbol.replace(/USDT$/i, '').replace(/USD$/i, '')
}

function coinGlyph(base: string): string {
  if (base === 'BTC') return '₿'
  return base.charAt(0)
}

function coinClass(base: string): string {
  if (base === 'ETH' || base === 'LINK') return 'eth'
  if (base === 'SOL') return 'sol'
  return ''
}

function cycleTag(r: ScreenerDecisionRow): { label: string; tone: string } {
  const bucket = verdictBucket(r)
  if (bucket === 'buy') {
    if (r.decision === 'STRONG_BUY' || r.confidence >= 0.8) {
      return { label: 'TRIGGERED', tone: 'amber' }
    }
    return { label: 'ARMED', tone: '' }
  }
  if (bucket === 'sell' || bucket === 'watch') return { label: 'WATCH', tone: '' }
  return { label: 'WATCH', tone: 'gray' }
}

function opportunityHint(r: ScreenerDecisionRow): string {
  const bucket = verdictBucket(r)
  if (bucket === 'buy' && (r.rvol == null || r.rvol < 1.5)) {
    return 'En attente de confirmation RVOL'
  }
  if (bucket === 'buy') return 'Toutes les portes sont passées'
  if (bucket === 'sell') return 'Signal vendeur — short désactivé'
  return 'Structure à confirmer'
}

function positionNotional(p: PaperOverviewPosition): number {
  if (p.market_value != null && Number.isFinite(p.market_value)) return Math.abs(p.market_value)
  if (p.notional != null && Number.isFinite(p.notional)) return Math.abs(p.notional)
  return 0
}

function maxDrawdownPct(points: { equity: number }[], initial: number): number | null {
  if (!points.length) return null
  let peak = initial
  let maxDd = 0
  for (const p of points) {
    peak = Math.max(peak, p.equity)
    if (peak > 0) maxDd = Math.max(maxDd, (peak - p.equity) / peak)
  }
  return maxDd
}

function Tag({ children, tone = '' }: { children: ReactNode; tone?: string }) {
  return <span className={`tag${tone ? ` ${tone}` : ''}`}>{children}</span>
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
  warn,
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
        <span className={`mono${warn ? ' warn' : ''}`}>{value}</span>
      </div>
      <div className="track">
        <span style={{ width: `${width}%`, ...(warn ? { background: '#b99557' } : {}) }} />
      </div>
    </>
  )
}

function DeskRing({
  parts,
  value,
  label,
}: {
  parts: { pct: number; color: string }[]
  value: string
  label: string
}) {
  let offset = 0
  return (
    <div className="desk-ring">
      <svg viewBox="0 0 200 200" role="img" aria-label={`${label} : ${value}`}>
        <circle cx="100" cy="100" r="80" fill="none" stroke="#eeeae3" strokeWidth="19" />
        {parts.map((p, i) => {
          const o = offset
          offset += p.pct
          if (p.pct <= 0) return null
          return (
            <circle
              key={i}
              cx="100"
              cy="100"
              r="80"
              pathLength="100"
              fill="none"
              stroke={p.color}
              strokeWidth="19"
              strokeDasharray={`${p.pct} ${100 - p.pct}`}
              strokeDashoffset={-o}
              transform="rotate(-90 100 100)"
            />
          )
        })}
      </svg>
      <div>
        <b>{value}</b>
        <small>{label}</small>
      </div>
    </div>
  )
}

function EquityChart({
  points,
  initial,
}: {
  points: { t: string; equity: number }[]
  initial: number
}) {
  if (points.length < 2) {
    return (
      <div className="chart-summary" style={{ padding: '40px 20px' }}>
        <span>Courbe en construction</span>
      </div>
    )
  }
  const vals = points.map((p) => p.equity)
  const min = Math.min(...vals, initial)
  const max = Math.max(...vals, initial)
  const span = Math.max(1e-6, max - min)
  const left = 25
  const right = 680
  const top = 20
  const bottom = 210
  const path = vals
    .map((v, i) => {
      const x = left + (i / (vals.length - 1)) * (right - left)
      const y = bottom - ((v - min) / span) * (bottom - top)
      return `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
  const lastY = bottom - ((vals[vals.length - 1] - min) / span) * (bottom - top)
  const gridYs = [45, 95, 145, 195]
  const labels = [0, 0.25, 0.5, 0.75, 1].map((t) => {
    const idx = Math.min(vals.length - 1, Math.floor(t * (vals.length - 1)))
    const d = new Date(points[idx].t)
    return Number.isNaN(d.getTime())
      ? '—'
      : d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' }).toUpperCase()
  })

  return (
    <>
      <svg className="chart" viewBox="0 0 720 230" role="img" aria-label="Courbe de performance">
        <defs>
          <linearGradient id="desk-equity-fade" x1="0" y1="0" x2="0" y2="1">
            <stop stopColor="#b5d6cc" stopOpacity=".35" />
            <stop offset="1" stopColor="#b5d6cc" stopOpacity="0" />
          </linearGradient>
        </defs>
        {gridYs.map((y, i) => (
          <g key={y}>
            <line x1="25" y1={y} x2="680" y2={y} stroke="#eeeae5" strokeDasharray="3 5" />
            <text x="684" y={y + 3} fontSize="9" fill="#939a9d">
              {fmtEur(max - (i / (gridYs.length - 1)) * (max - min), 0)}
            </text>
          </g>
        ))}
        <path d={`${path} L680,210 L25,210Z`} fill="url(#desk-equity-fade)" />
        <path d={path} fill="none" stroke="#478f83" strokeWidth="2" />
        <circle cx="680" cy={lastY} r="4" fill="#478f83" />
      </svg>
      <div className="chart-labels">
        {labels.map((l, i) => (
          <span key={`${l}-${i}`}>{l}</span>
        ))}
      </div>
    </>
  )
}

export function OverviewPage() {
  const [rows, setRows] = useState<ScreenerDecisionRow[]>([])
  const [cacheAge, setCacheAge] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [overview, setOverview] = useState<PaperOverview | null>(null)
  const [summary, setSummary] = useState<ActivitySummary | null>(null)
  const [tape, setTape] = useState<ActivityItem[]>([])
  const [evidence, setEvidence] = useState<BacktestEvidenceSummary | null>(null)
  const [portfolios, setPortfolios] = useState<PaperPortfolioRow[]>([])
  const [deskSession, setDeskSession] = useState(1)
  const [period, setPeriod] = useState<Period>('1M')

  const load = useCallback(async (force = false) => {
    setLoading(true)
    type ScreenerOk = Awaited<ReturnType<typeof getScreener>>
    const [screenerRes, ovRes, sumRes, feedRes, evRes, pfRes] = await Promise.all([
      getScreener('1h', force)
        .then((r): ScreenerOk | Error => r)
        .catch((err: unknown): ScreenerOk | Error =>
          err instanceof Error ? err : new Error('Screener indisponible'),
        ),
      getPaperOverview(BASELINE).catch(() => null),
      getActivitySummary().catch(() => null),
      getActivityFeed(40).catch(() => ({ items: [] as ActivityItem[] })),
      getBacktestEvidence().catch(() => null),
      listPaperPortfolios().catch(() => [] as PaperPortfolioRow[]),
    ])

    if (screenerRes instanceof Error) {
      const msg = screenerRes.message
      setError(
        msg.includes('engine_unreachable') || msg.includes('502')
          ? 'Moteur Python injoignable — lance l’engine pour le desk.'
          : msg,
      )
      setRows([])
      setCacheAge(null)
    } else {
      setError(null)
      setRows(screenerRes.rows)
      setCacheAge(screenerRes.cache_age_seconds)
    }

    setOverview(ovRes)
    setSummary(sumRes)
    setTape(feedRes.items.slice(0, TAPE_LIMIT))
    setEvidence(evRes)
    setPortfolios(pfRes.filter((p) => p.is_active))
    setLoading(false)
  }, [])

  useEffect(() => {
    void load()
    const id = window.setInterval(() => void load(), REFRESH_MS)
    return () => window.clearInterval(id)
  }, [load])

  const stats = useMemo(() => summarize(rows), [rows])
  const acct = overview?.account
  const openBook = overview?.positions ?? []

  const dayPct =
    acct?.day_change != null && acct.equity
      ? acct.day_change / Math.max(1e-9, acct.equity - acct.day_change)
      : null

  const availablePct = acct != null && acct.equity > 0 ? acct.cash / acct.equity : null
  const exposedPct = acct != null && acct.equity > 0 ? acct.invested / acct.equity : null
  const riskPct = overview?.risk?.open_risk_pct ?? null
  const riskCap = overview?.risk?.max_open_risk_pct ?? 0.03

  const drawdown = useMemo(
    () => maxDrawdownPct(overview?.equity_curve ?? [], acct?.initial_cash ?? 5000),
    [overview?.equity_curve, acct?.initial_cash],
  )

  const equityPoints = useMemo(() => {
    const curve = overview?.equity_curve ?? []
    if (!curve.length) return curve
    const now = Date.now()
    const ms =
      period === '1J'
        ? 86_400_000
        : period === '1S'
          ? 7 * 86_400_000
          : period === '1M'
            ? 30 * 86_400_000
            : 90 * 86_400_000
    const filtered = curve.filter((p) => {
      const t = Date.parse(p.t)
      return !Number.isNaN(t) && now - t <= ms
    })
    return filtered.length >= 2 ? filtered : curve
  }, [overview?.equity_curve, period])

  const tickers = useMemo(
    () => [...rows].sort((a, b) => b.confidence - a.confidence).slice(0, 4),
    [rows],
  )

  const watchList = useMemo(() => {
    if (stats.top.length) return stats.top.slice(0, 3)
    return [...rows].sort((a, b) => b.confidence - a.confidence).slice(0, 3)
  }, [stats.top, rows])

  const nextCheckpoint = useMemo(() => {
    return (
      rows.find((r) => {
        const b = verdictBucket(r)
        return b === 'buy' && (r.rvol == null || r.rvol < 1.5)
      }) ??
      watchList[0] ??
      null
    )
  }, [rows, watchList])

  const concentration = useMemo(() => {
    const total = openBook.reduce((s, p) => s + positionNotional(p), 0)
    if (total <= 0) return []
    return [...openBook]
      .map((p) => ({
        symbol: displaySymbol(p.symbol),
        pct: (positionNotional(p) / total) * 100,
      }))
      .sort((a, b) => b.pct - a.pct)
      .slice(0, 6)
  }, [openBook])

  const session = DESK_SESSIONS[deskSession]
  const todayLabel = new Date().toLocaleDateString('fr-FR', {
    day: 'numeric',
    month: 'long',
  })

  const dayTone =
    acct?.day_change != null && acct.day_change > 0
      ? 'up'
      : acct?.day_change != null && acct.day_change < 0
        ? 'down'
        : ''

  const riskOk = riskPct == null || riskPct <= riskCap
  const maxPos = overview?.risk?.max_open_positions ?? 6
  const openPos = acct?.open_positions ?? openBook.length
  const engineOk = !error
  const activeLabs = portfolios.length
  const edgeHint = evidence?.pipeline_beats_ichimoku_sharpe

  return (
    <>
      <header className="page-head">
        <div>
          <div className="eyebrow">{workspaceEyebrow('/app/desk')}</div>
          <h1>Desk</h1>
          <p className="subtitle">Votre marché, en un regard.</p>
        </div>
        <div className="actions">
          <span className="subtitle">{todayLabel} · aperçu</span>
          <Link to="/app/market" className="link" style={{ marginLeft: 14 }}>
            Ouvrir le marché ↗
          </Link>
          <button type="button" onClick={() => void load(true)} style={{ marginLeft: 10 }}>
            Actualiser
          </button>
        </div>
      </header>

      <div className="desk-workspace">
        <div className="metrics">
          <div className="metric featured">
            <div className="metric-label">
              Capital total<span>↗</span>
            </div>
            <div className="metric-value">{acct ? fmtEur(acct.equity) : '—'}</div>
            <small>Portefeuille paper · EUR</small>
          </div>
          <div className="metric">
            <div className="metric-label">
              Disponible<span>↗</span>
            </div>
            <div className="metric-value">{acct ? fmtEur(acct.cash) : '—'}</div>
            <small>
              {availablePct != null
                ? `${(availablePct * 100).toFixed(1).replace('.', ',')} % du capital`
                : '—'}
            </small>
          </div>
          <div className={`metric${dayTone === 'up' ? ' up' : dayTone === 'down' ? ' down' : ''}`}>
            <div className="metric-label">
              P&L du jour<span>↗</span>
            </div>
            <div className="metric-value">
              {acct?.day_change != null ? fmtEur(acct.day_change) : '—'}
            </div>
            <small>
              {dayPct != null
                ? `${dayPct > 0 ? '↗' : dayPct < 0 ? '↘' : '→'} ${fmtPct(dayPct)} aujourd’hui`
                : '—'}
            </small>
          </div>
          <div className="metric">
            <div className="metric-label">
              Risque utilisé<span>↗</span>
            </div>
            <div className="metric-value">
              {riskPct != null ? `${(riskPct * 100).toFixed(1).replace('.', ',')} %` : '—'}
            </div>
            <small>Limite : {((riskCap ?? 0.03) * 100).toFixed(0)} %</small>
          </div>
        </div>

        <div className="desk-overview">
          <section className="card world-card">
            <div className="card-head">
              <h2>Sessions de marché</h2>
              <Tag tone="gray">APERÇU</Tag>
            </div>
            <div className="world-view">
              <img
                src="/world-map.svg"
                alt="Carte du monde situant les sessions de Londres, New York et Tokyo"
                width={720}
                height={290}
              />
              {DESK_SESSIONS.map((s, i) => (
                <button
                  key={s.city}
                  type="button"
                  className={`map-marker${i === deskSession ? ' selected' : ''}`}
                  style={{ left: `${s.left}%`, top: `${s.top}%` }}
                  aria-label={`Session ${s.city}`}
                  aria-pressed={i === deskSession}
                  onClick={() => setDeskSession(i)}
                >
                  <span />
                  <b>{s.city}</b>
                </button>
              ))}
            </div>
            <div className="session-selector">
              {DESK_SESSIONS.map((s, i) => (
                <button
                  key={s.region}
                  type="button"
                  className={i === deskSession ? 'active' : undefined}
                  aria-pressed={i === deskSession}
                  onClick={() => setDeskSession(i)}
                >
                  {s.region}
                  <small>{s.status}</small>
                </button>
              ))}
            </div>
            <div className="session-detail">
              <strong>
                {session.city}{' '}
                <span className={deskSession === 1 ? 'up' : 'muted'}>{session.status}</span>
              </strong>
              <span className="mono">{session.hours}</span>
            </div>
            <div className="map-foot">
              Sessions illustratives · horaires de l’aperçu{' '}
              <span>
                Crypto <b>24/7</b>
              </span>
            </div>
          </section>

          <section className="card">
            <div className="card-head">
              <h2>Marchés principaux</h2>
              <Tag tone="gray">{tickers.length ? 'LIVE' : '—'}</Tag>
            </div>
            <div className="desk-tickers">
              {tickers.length === 0 ? (
                <div className="desk-ticker" style={{ pointerEvents: 'none' }}>
                  <span>
                    <b>
                      —<small> / USDT</small>
                    </b>
                    <small>Aucun ticker</small>
                  </span>
                  <span className="right">
                    <b className="mono">—</b>
                    <small>—</small>
                  </span>
                </div>
              ) : (
                tickers.map((r) => {
                  const base = displaySymbol(r.symbol)
                  return (
                    <Link
                      key={r.symbol}
                      to={`/app/market?symbol=${encodeURIComponent(r.symbol)}`}
                      className="desk-ticker"
                    >
                      <span>
                        <b>
                          {base}
                          <small> / USDT</small>
                        </b>
                        <small>{r.timeframe}</small>
                      </span>
                      <span className="right">
                        <b className="mono">{fmtPrice(r.price)}</b>
                        <small>{r.rvol != null ? `RVOL ${r.rvol.toFixed(1)}×` : '—'}</small>
                      </span>
                    </Link>
                  )
                })
              )}
            </div>
            <div className="card-foot">
              <Link to="/app/market" className="link">
                Tout le marché ↗
              </Link>
            </div>
          </section>

          <section className="card">
            <div className="card-head">
              <h2>Lecture du marché</h2>
            </div>
            <div className="card-body">
              <div className="climate-head">
                <span className="climate-symbol">↗</span>
                <div>
                  <small>RÉGIME DE L’APERÇU</small>
                  <h3>
                    {stats.buy > stats.sell ? 'Tendance' : stats.sell > stats.buy ? 'Prudence' : 'Neutre'}
                  </h3>
                </div>
              </div>
              <StatLine
                label="Volatilité"
                value={stats.total ? (stats.watch > stats.total * 0.4 ? 'Élevée' : 'Modérée') : '—'}
              />
              <StatLine label="Signaux BUY" value={stats.total ? String(stats.buy) : '—'} />
              <StatLine
                label="Concentration"
                value={
                  <Tag tone={openPos >= 3 ? 'amber' : 'gray'}>
                    {openPos >= 3 ? 'PRUDENCE' : openPos > 0 ? 'OK' : '—'}
                  </Tag>
                }
              />
              <p className="desk-note">
                Le contexte éclaire le signal. Le risque garde le dernier mot.
              </p>
              <Link to="/app/context" className="link">
                Ouvrir le contexte ↗
              </Link>
            </div>
          </section>
        </div>

        <div className="grid">
          <section className="card">
            <div className="card-head">
              <h2>Trajectoire du portefeuille</h2>
              <div className="segmented">
                {PERIODS.map((p) => (
                  <button
                    key={p}
                    type="button"
                    className={p === period ? 'active' : undefined}
                    onClick={() => setPeriod(p)}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
            <div className="chart-summary">
              <span>
                CAPITAL <b>{acct ? fmtEur(acct.equity) : '—'}</b>
              </span>
              <span>
                DRAWDOWN{' '}
                <b className="down">
                  {drawdown != null
                    ? `−${(drawdown * 100).toFixed(1).replace('.', ',')} %`
                    : '—'}
                </b>
              </span>
            </div>
            <div id="equity">
              <EquityChart points={equityPoints} initial={acct?.initial_cash ?? 5000} />
            </div>
          </section>

          <section className="card">
            <div className="card-head">
              <h2>À surveiller</h2>
              <Tag tone="gray">{watchList.length ? `${watchList.length} SÉLECTIONS` : '—'}</Tag>
            </div>
            <div className="card-body">
              {watchList.length === 0 ? (
                <p className="desk-note">{loading ? 'Scan screener…' : 'Aucune sélection.'}</p>
              ) : (
                watchList.map((r) => {
                  const base = displaySymbol(r.symbol)
                  const tag = cycleTag(r)
                  const score = Math.round(r.confidence * 100)
                  const extra = coinClass(base)
                  return (
                    <Link
                      key={r.symbol}
                      to={`/app/opportunites?symbol=${encodeURIComponent(r.symbol)}`}
                      className="opportunity"
                    >
                      <span className={`coin${extra ? ` ${extra}` : ''}`}>{coinGlyph(base)}</span>
                      <div>
                        <strong>
                          {base}
                          <span style={{ color: '#a0a4a6', fontWeight: 400 }}> / USDT</span>
                        </strong>
                        <small>{opportunityHint(r)}</small>
                      </div>
                      <div className="right">
                        <span className="score">
                          {score}
                          <small style={{ display: 'inline' }}> /100</small>
                        </span>
                        <small>
                          <Tag tone={tag.tone}>{tag.label}</Tag>
                        </small>
                      </div>
                    </Link>
                  )
                })
              )}
            </div>
            <div className="card-foot">
              <Link className="link" to="/app/opportunites">
                Explorer les opportunités ↗
              </Link>
            </div>
          </section>
        </div>

        <div className="notice">
          <span>△</span>
          <span>
            {error ? (
              <>
                <b>Une donnée demande votre attention.</b> {error}
              </>
            ) : cacheAge != null && cacheAge > 3600 ? (
              <>
                <b>Une donnée demande votre attention.</b> Screener : dernière mise à jour{' '}
                {fmtCacheAge(cacheAge)}.
              </>
            ) : (
              <>
                <b>Desk à jour.</b>{' '}
                {cacheAge != null
                  ? `Screener ${fmtCacheAge(cacheAge)}.`
                  : 'En attente du screener.'}
              </>
            )}
          </span>
          <Link to="/app/operations">Vérifier →</Link>
        </div>

        <div className="grid">
          <section className="card">
            <div className="card-head">
              <h2>Positions ouvertes</h2>
              <Link className="link" to="/app/portefeuille">
                Portefeuille ↗
              </Link>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>ACTIF / STRATÉGIE</th>
                    <th>ENGAGÉ</th>
                    <th>PERFORMANCE</th>
                    <th>P&L LATENT</th>
                    <th>ÉTAT</th>
                  </tr>
                </thead>
                <tbody>
                  {openBook.length === 0 ? (
                    <tr>
                      <td colSpan={5}>—</td>
                    </tr>
                  ) : (
                    openBook.map((p) => {
                      const perf = p.unrealized_pct
                      const pnl = p.unrealized_pnl
                      return (
                        <tr key={p.id} className="clickable">
                          <td>
                            <b>{displaySymbol(p.symbol)}</b>
                            <small>Ichimoku × RVOL · {p.timeframe}</small>
                          </td>
                          <td>
                            <span className="mono">{fmtEur(positionNotional(p))}</span>
                          </td>
                          <td>
                            <span
                              className={`mono${
                                perf != null && perf > 0
                                  ? ' up'
                                  : perf != null && perf < 0
                                    ? ' down'
                                    : ''
                              }`}
                            >
                              {fmtPct(perf)}
                            </span>
                          </td>
                          <td>
                            <span
                              className={`mono${
                                pnl != null && pnl > 0 ? ' up' : pnl != null && pnl < 0 ? ' down' : ''
                              }`}
                            >
                              {fmtEur(pnl)}
                            </span>
                          </td>
                          <td>
                            <Tag tone="green">OUVERTE</Tag>
                          </td>
                        </tr>
                      )
                    })
                  )}
                </tbody>
              </table>
            </div>
          </section>

          <section className="card">
            <div className="card-head">
              <h2>Votre budget de risque</h2>
              <Tag tone={riskOk ? '' : 'red'}>{riskOk ? 'PASSE' : 'REFUSÉ'}</Tag>
            </div>
            <div className="card-body">
              <ProgressRow
                label="Exposition du capital"
                value={
                  exposedPct != null
                    ? `${(exposedPct * 100).toFixed(1).replace('.', ',')} %`
                    : '—'
                }
                pct={exposedPct != null ? exposedPct * 100 : 0}
              />
              <ProgressRow
                label="Risque journalier"
                value={
                  riskPct != null
                    ? `${(riskPct * 100).toFixed(1)} / ${(riskCap * 100).toFixed(0)} %`
                    : '—'
                }
                pct={riskPct != null && riskCap > 0 ? (riskPct / riskCap) * 100 : 0}
              />
              <ProgressRow
                label="Positions simultanées"
                value={`${openPos} / ${maxPos}`}
                pct={maxPos > 0 ? (openPos / maxPos) * 100 : 0}
              />
              <div style={{ marginTop: 20, fontSize: 10, color: 'var(--muted)' }}>
                {acct
                  ? `${fmtEur(acct.invested)} engagés sur ${openPos} position${openPos === 1 ? '' : 's'}.`
                  : '—'}
              </div>
            </div>
          </section>
        </div>

        <div className="grid three">
          <section className="card">
            <div className="card-head">
              <h2>Derniers événements</h2>
            </div>
            <div className="card-body">
              <div className="timeline">
                {tape.length === 0 ? (
                  <div className="event">
                    Aucun événement récent
                    <small>—</small>
                  </div>
                ) : (
                  tape.slice(0, 3).map((it) => (
                    <div key={`${it.time}-${it.kind}-${it.symbol}-${it.detail}`} className="event">
                      {it.title}
                      <small>
                        {fmtClock(it.time)} · {it.detail}
                      </small>
                    </div>
                  ))
                )}
              </div>
            </div>
          </section>

          <section className="card">
            <div className="card-head">
              <h2>Le prochain contrôle</h2>
            </div>
            <div className="card-body">
              <div className="checkpoint">
                <span className="checkpoint-icon">◇</span>
                <div>
                  <b>Clôture 1H</b>
                  <small>Confirmer avant d’agir</small>
                </div>
              </div>
              <StatLine
                label={
                  nextCheckpoint
                    ? `${displaySymbol(nextCheckpoint.symbol)} · participation`
                    : 'Participation'
                }
                value={
                  nextCheckpoint?.rvol != null ? (
                    <Tag tone={nextCheckpoint.rvol >= 1.5 ? '' : 'amber'}>
                      RVOL {nextCheckpoint.rvol.toFixed(1)}×
                    </Tag>
                  ) : (
                    <Tag tone="gray">—</Tag>
                  )
                }
              />
              <StatLine label="Seuil attendu" value="≥ 1,5×" />
              <p className="desk-note">
                {nextCheckpoint
                  ? `Le volume reste à confirmer sur ${displaySymbol(nextCheckpoint.symbol)}. La confiance ne remplace pas les portes de décision.`
                  : 'Aucune confirmation en attente pour le moment.'}
              </p>
              <Link className="link" to="/app/opportunites">
                Examiner les confirmations →
              </Link>
            </div>
          </section>

          <section className="card">
            <div className="card-head">
              <h2>État du système</h2>
            </div>
            <div className="card-body">
              <StatLine
                label="Moteur Python"
                value={
                  <Tag tone={engineOk ? 'green' : 'gray'}>
                    {engineOk ? 'CONNECTÉ' : 'NON CONNECTÉ'}
                  </Tag>
                }
              />
              <StatLine
                label="Source des données"
                value={
                  <Tag tone="gray">
                    {cacheAge != null ? `SCREENER · ${fmtCacheAge(cacheAge)}` : '—'}
                  </Tag>
                }
              />
              <StatLine
                label="Risk Kernel"
                value={<Tag tone={riskOk ? '' : 'red'}>{riskOk ? 'PASSE' : 'REFUSÉ'}</Tag>}
              />
              <StatLine label="Exécution réelle" value={<Tag tone="red">BLOQUÉE</Tag>} />
              {summary ? (
                <StatLine
                  label="Décisions 24 h"
                  value={<b className="mono">{summary.decisions.last_24h}</b>}
                />
              ) : null}
              {edgeHint ? (
                <StatLine
                  label="Edge Lab"
                  value={
                    <Tag tone="gray">
                      {edgeHint.beats}/{edgeHint.compared}
                    </Tag>
                  }
                />
              ) : null}
              {activeLabs > 0 ? (
                <StatLine label="Labs paper" value={<b className="mono">{activeLabs}</b>} />
              ) : null}
            </div>
          </section>
        </div>

        <div className="desk-allocation">
          <section className="card">
            <div className="card-head">
              <h2>Répartition du capital</h2>
              <Tag tone="gray">{acct ? fmtEur(acct.equity, 0) : '—'}</Tag>
            </div>
            <div className="allocation-body">
              <DeskRing
                parts={[
                  {
                    pct: exposedPct != null ? exposedPct * 100 : 0,
                    color: '#548f87',
                  },
                ]}
                value={
                  exposedPct != null
                    ? `${(exposedPct * 100).toFixed(1).replace('.', ',')} %`
                    : '—'
                }
                label="Capital engagé"
              />
              <div className="allocation-legend">
                <StatLine
                  label={
                    <>
                      <span className="legend-dot teal" />
                      Engagé
                    </>
                  }
                  value={acct ? fmtEur(acct.invested) : '—'}
                />
                <StatLine
                  label={
                    <>
                      <span className="legend-dot neutral" />
                      Disponible
                    </>
                  }
                  value={acct ? fmtEur(acct.cash) : '—'}
                />
                <p className="desk-note">
                  {availablePct != null
                    ? `${(availablePct * 100).toFixed(1).replace('.', ',')} % du capital reste disponible.`
                    : '—'}
                </p>
              </div>
            </div>
            <div className="card-foot">
              <Link to="/app/portefeuille" className="link">
                Voir l’allocation ↗
              </Link>
            </div>
          </section>

          <section className="card">
            <div className="card-head">
              <h2>Concentration des positions</h2>
              <Tag tone={concentration.length >= 3 ? 'amber' : 'gray'}>
                {concentration.length >= 3
                  ? 'PRUDENCE'
                  : concentration.length
                    ? String(concentration.length)
                    : '—'}
              </Tag>
            </div>
            <div className="allocation-body">
              <DeskRing
                parts={concentration.map((c, i) => ({
                  pct: c.pct,
                  color: RING_COLORS[i % RING_COLORS.length],
                }))}
                value={String(openPos || '—')}
                label="Positions ouvertes"
              />
              <div className="allocation-legend">
                {concentration.length === 0 ? (
                  <p className="desk-note">Pas d’exposition ouverte.</p>
                ) : (
                  concentration.map((c, i) => (
                    <Link
                      key={c.symbol}
                      to="/app/portefeuille?tab=positions"
                      className="concentration-row"
                    >
                      <span>
                        <i style={{ background: RING_COLORS[i % RING_COLORS.length] }} />
                        {c.symbol}
                      </span>
                      <b className="mono">{c.pct.toFixed(1).replace('.', ',')} %</b>
                    </Link>
                  ))
                )}
                <p className="desk-note">100 % de l’exposition en crypto spot.</p>
              </div>
            </div>
            <div className="card-foot">
              <Link to="/app/portefeuille" className="link">
                Surveiller la concentration ↗
              </Link>
            </div>
          </section>
        </div>
      </div>
    </>
  )
}
