/**
 * Desk — port littéral de design-reference/ichivol-workspace `desk()` + page-head.
 * Classes HTML = maquette. Données = engine (pas de démo inventée ; manquant → « — »).
 */

import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
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
  nextHourlyClose,
  sessionStatus,
  sessionStatusLabel,
  type SessionId,
  type SessionStatus,
} from '../lib/marketSessions'
import {
  getPaperOverview,
  type PaperOverview,
  type PaperOverviewPosition,
} from '../lib/paper'
import { getRiskLock, type RiskLockState } from '../lib/riskLock'
import { verdictBucket } from '../lib/deskSummarize'
import { concentrationFromPositions } from '../components/desk/DeskRings'
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

function filterEquityCurve(
  points: { t: string; equity: number }[],
  period: EquityPeriod,
  now = Date.now(),
): { t: string; equity: number }[] {
  const ms =
    period === '1J'
      ? 86_400_000
      : period === '1S'
        ? 7 * 86_400_000
        : period === '1M'
          ? 30 * 86_400_000
          : 90 * 86_400_000
  const cutoff = now - ms
  return points.filter((p) => {
    const t = Date.parse(p.t)
    return !Number.isNaN(t) && t >= cutoff
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
}: {
  points: { t: string; equity: number }[]
  period: EquityPeriod
}) {
  const filtered = filterEquityCurve(points, period)
  if (filtered.length < 2) {
    return (
      <div id="equity">
        <svg
          className="chart"
          viewBox="0 0 720 230"
          role="img"
          aria-label="Courbe de performance indisponible"
        />
      </div>
    )
  }
  const vals = filtered.map((p) => p.equity)
  const min = Math.min(...vals)
  const max = Math.max(...vals)
  const span = Math.max(1e-6, max - min)
  const w = 720
  const h = 230
  const padL = 25
  const padR = 46
  const padT = 20
  const padB = 30
  const innerW = w - padL - padR
  const innerH = h - padT - padB
  const coords = vals.map((v, i) => {
    const x = padL + (i / (vals.length - 1)) * innerW
    const y = padT + (1 - (v - min) / span) * innerH
    return [x, y] as const
  })
  const d = coords.map((p, i) => `${i ? 'L' : 'M'}${p[0]},${p[1]}`).join(' ')
  const last = coords[coords.length - 1]
  const area = `${d} L${last[0]},${h - padB} L${padL},${h - padB}Z`
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
    <div id="equity">
      <svg className="chart" viewBox={`0 0 ${w} ${h}`} role="img" aria-label={`Courbe equity ${period}`}>
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
        <circle cx={last[0]} cy={last[1]} r="4" fill="#478f83" />
      </svg>
      <div className="chart-labels">
        {labels.map((l, i) => (
          <span key={`${l}-${i}`}>{l}</span>
        ))}
      </div>
    </div>
  )
}

export function OverviewPage() {
  const navigate = useNavigate()
  const [rows, setRows] = useState<ScreenerDecisionRow[]>([])
  const [loading, setLoading] = useState(true)
  const [overview, setOverview] = useState<PaperOverview | null>(null)
  const [tape, setTape] = useState<ActivityItem[]>([])
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
    const [screenerRes, ovRes, feedRes, lockRes, healthRes, mktRes, fngRes, tickersRes] =
      await Promise.all([
        getScreener('1h', force)
          .then((r): ScreenerOk | Error => r)
          .catch((err: unknown): ScreenerOk | Error =>
            err instanceof Error ? err : new Error('Screener indisponible'),
          ),
        getPaperOverview(BASELINE)
          .then((r) => ({ ok: true as const, data: r }))
          .catch(() => ({ ok: false as const })),
        getActivityFeed(40)
          .then((r) => ({ ok: true as const, items: r.items }))
          .catch(() => ({ ok: false as const, items: [] as ActivityItem[] })),
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

    if (feedRes.ok) setTape(feedRes.items.slice(0, TAPE_LIMIT))
    else setTape([])

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
    topConc == null ? '—' : topConc >= 40 ? 'PRUDENCE' : 'OK'

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
                ? `Limite : ${fmtPct(risk.max_open_risk_pct, 0, false)}`
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
            <EquityViz points={overview?.equity_curve ?? []} period={equityPeriod} />
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

        {freshnessIssues.length > 0 ? (
          <div className="notice">
            <span>△</span>
            <span>
              <b>Une donnée demande votre attention.</b>{' '}
              {freshnessIssues.slice(0, 4).join(', ')}
              {freshnessIssues.length > 4 ? ` (+${freshnessIssues.length - 4})` : ''} : fraîcheur
              ou mark périmé.
            </span>
            <Link to="/app/operations">Vérifier →</Link>
          </div>
        ) : null}

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
                  {(overview?.positions ?? []).map((p: PaperOverviewPosition) => {
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
                  tape.map((it) => (
                    <div
                      key={`${it.time}-${it.kind}-${it.symbol}-${it.portfolio}-${it.detail}`}
                      className="event"
                    >
                      {it.title}
                      <small>
                        {fmtClock(it.time)} · {it.detail || '—'}
                      </small>
                    </div>
                  ))
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
                  {(() => {
                    let offset = 0
                    return concentration.slice(0, 5).map((c, i) => {
                      const o = offset
                      offset += c.pct
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
                    })
                  })()}
                </svg>
                <div>
                  <b>{concentration.length ? String(concentration.length) : '—'}</b>
                  <small>Positions ouvertes</small>
                </div>
              </div>
              <div className="allocation-legend">
                {concentration.slice(0, 5).map((c, i) => (
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
