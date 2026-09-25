import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { VerdictBadge } from '../components/VerdictBadge'
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
  formatSessionHoursLocal,
  nextHourlyClose,
  sessionStatus,
  sessionStatusLabel,
  type MarketSessionDef,
  type SessionId,
} from '../lib/marketSessions'
import {
  getPaperOverview,
  type PaperOverview,
  type PaperOverviewPosition,
} from '../lib/paper'
import { getRiskLock, type RiskLockState } from '../lib/riskLock'
import { verdictBucket } from '../lib/deskSummarize'
import './OverviewPage.css'

const BASELINE = 'ICHIVOL_BASELINE_V1'
const REFRESH_MS = 60_000
const TAPE_LIMIT = 8
const PRIMARY_SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'LINKUSDT']

type EquityPeriod = '1J' | '1S' | '1M' | '3M'

/** Percentage already expressed as percent units (e.g. 58.5), not ratio. */
function fmtPctPoints(
  v: number | null | undefined,
  digits = 1,
  signed = false,
): string {
  if (v == null || Number.isNaN(v)) return '—'
  const n = new Intl.NumberFormat('fr-FR', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
    signDisplay: signed ? 'exceptZero' : 'auto',
  }).format(v)
  return `${n} %`
}

/** Ratio 0–1 → pourcentage fr-FR (ex. 0.585 → « 58,5 % »). */
function fmtPct(v: number | null | undefined, digits = 1, signed = true): string {
  if (v == null || Number.isNaN(v)) return '—'
  return fmtPctPoints(v * 100, digits, signed)
}

function fmtDec(v: number | null | undefined, digits = 2): string {
  if (v == null || Number.isNaN(v)) return '—'
  return new Intl.NumberFormat('fr-FR', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(v)
}

function fmtEur(v: number | null | undefined, digits = 0): string {
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
  if (v >= 1000) {
    return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 }).format(v)
  }
  if (v >= 1) {
    return new Intl.NumberFormat('fr-FR', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(v)
  }
  return new Intl.NumberFormat('fr-FR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 5,
  }).format(v)
}

function fmtClock(iso: string): string {
  return new Date(iso).toLocaleTimeString('fr-FR', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

function toneClass(tone: ActivityItem['tone']): string {
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

function EquityChart({
  points,
  initial,
  period,
  onPeriod,
}: {
  points: { t: string; equity: number }[]
  initial: number
  period: EquityPeriod
  onPeriod: (p: EquityPeriod) => void
}) {
  const filtered = filterEquityCurve(points, period)
  return (
    <div className="desk-equity">
      <div className="desk-equity-periods" role="group" aria-label="Période">
        {(['1J', '1S', '1M', '3M'] as const).map((p) => (
          <button
            key={p}
            type="button"
            className={period === p ? 'is-active' : undefined}
            onClick={() => onPeriod(p)}
          >
            {p}
          </button>
        ))}
      </div>
      {filtered.length < 2 ? (
        <div className="ov-spark ov-spark--empty muted">Courbe en construction</div>
      ) : (
        (() => {
          const vals = filtered.map((p) => p.equity)
          const min = Math.min(...vals, initial)
          const max = Math.max(...vals, initial)
          const span = Math.max(1e-6, max - min)
          const w = 640
          const h = 160
          const poly = vals
            .map((v, i) => {
              const x = (i / (vals.length - 1)) * w
              const y = h - ((v - min) / span) * (h - 8) - 4
              return `${x.toFixed(1)},${y.toFixed(1)}`
            })
            .join(' ')
          const up = vals[vals.length - 1] >= initial
          return (
            <svg
              className={`desk-equity-svg ${up ? 'is-up' : 'is-down'}`}
              viewBox={`0 0 ${w} ${h}`}
              role="img"
              aria-label={`Trajectoire equity ${period}`}
            >
              <polyline fill="none" strokeWidth="2" points={poly} />
            </svg>
          )
        })()
      )}
    </div>
  )
}

function Ring({
  parts,
  center,
  label,
}: {
  parts: { pct: number; color: string }[]
  center: string
  label: string
}) {
  const offsets: number[] = []
  let acc = 0
  for (const p of parts) {
    offsets.push(acc)
    acc += p.pct
  }
  return (
    <div className="desk-ring">
      <svg viewBox="0 0 200 200" role="img" aria-label={`${label} : ${center}`}>
        <circle cx="100" cy="100" r="80" fill="none" stroke="var(--line)" strokeWidth="19" />
        {parts.map((p, i) => (
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
            strokeDashoffset={-offsets[i]}
            transform="rotate(-90 100 100)"
          />
        ))}
      </svg>
      <div>
        <b>{center}</b>
        <small>{label}</small>
      </div>
    </div>
  )
}

function CardShell({
  title,
  meta,
  children,
  className,
  footer,
}: {
  title: string
  meta?: ReactNode
  children: ReactNode
  className?: string
  footer?: ReactNode
}) {
  return (
    <section className={`panel desk-card ${className ?? ''}`.trim()}>
      <header className="panel-head">
        <h2>{title}</h2>
        {meta ? <span className="panel-meta">{meta}</span> : null}
      </header>
      <div className="card-body">{children}</div>
      {footer ? <div className="card-foot">{footer}</div> : null}
    </section>
  )
}

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

  const selectedSession: MarketSessionDef =
    MARKET_SESSIONS.find((s) => s.id === sessionId) ?? MARKET_SESSIONS[1]

  const investedPct =
    acct && acct.equity > 0 ? Math.min(100, Math.max(0, (acct.invested / acct.equity) * 100)) : 0

  const concentration = useMemo(() => {
    const positions = overview?.positions ?? []
    const values = positions
      .map((p) => ({
        symbol: p.symbol.replace(/USDT$/i, ''),
        mv: Math.abs(p.market_value ?? (p.current_price != null ? p.current_price * (p.qty ?? 0) : 0)),
      }))
      .filter((p) => p.mv > 0)
    const total = values.reduce((s, v) => s + v.mv, 0)
    if (total <= 0) return [] as { symbol: string; pct: number }[]
    return values
      .map((v) => ({ symbol: v.symbol, pct: (v.mv / total) * 100 }))
      .sort((a, b) => b.pct - a.pct)
  }, [overview?.positions])

  const RING_COLORS = ['#548f87', '#8c9eb4', '#c2b596', '#a9bdb2', '#7d8288']

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

      {/* 1. KPIs */}
      <section className="iv-metrics desk-kpis iv-animate-in" aria-label="Indicateurs clés">
        <div className={`iv-metric${acct ? '' : ''}`}>
          <div className="iv-metric-label">Capital total</div>
          <div className="iv-metric-value mono">
            {loading && !acct ? '—' : acct ? fmtEur(acct.equity, 0) : '—'}
          </div>
          <small>Portefeuille paper · EUR</small>
        </div>
        <div className="iv-metric">
          <div className="iv-metric-label">Disponible</div>
          <div className="iv-metric-value mono">
            {acct ? fmtEur(acct.cash, 0) : '—'}
          </div>
          <small>
            {acct && acct.equity > 0
              ? `${fmtPct(acct.cash / acct.equity, 1, false)} du capital`
              : 'Cash libre'}
          </small>
        </div>
        <div className={`iv-metric${dayTone === 'bull' ? ' is-bull' : dayTone === 'bear' ? ' is-bear' : ''}`}>
          <div className="iv-metric-label">P&amp;L du jour</div>
          <div className="iv-metric-value mono">
            {acct?.day_change != null ? fmtEur(acct.day_change, 0) : '—'}
          </div>
          <small>{dayPct != null ? fmtPct(dayPct) : 'Variation journalière'}</small>
        </div>
        <div className="iv-metric">
          <div className="iv-metric-label">Risque utilisé</div>
          <div className="iv-metric-value mono">
            {risk?.open_risk_pct != null
              ? fmtPct(risk.open_risk_pct, 1, false)
              : risk
                ? fmtEur(risk.open_risk_amount, 0)
                : '—'}
          </div>
          <small>
            {risk?.max_open_risk_pct != null
              ? `Limite ${fmtPct(risk.max_open_risk_pct, 0, false)}`
              : 'Risque ouvert'}
          </small>
        </div>
      </section>
      {ovError && (
        <div className="banner error" role="alert">
          Compte paper : {ovError}
        </div>
      )}

      {/* 2–4. Overview row */}
      <div className="desk-overview iv-animate-in-delay">
        <CardShell title="Sessions de marché" meta="Horaires locaux · crypto 24/7">
          <div className="world-view">
            <img src="/world-map.svg" alt="" width={720} height={290} />
            {MARKET_SESSIONS.map((s) => {
              const st = sessionStatus(s, now)
              return (
                <button
                  key={s.id}
                  type="button"
                  className={`map-marker${sessionId === s.id ? ' selected' : ''}`}
                  style={{ left: `${s.mapLeftPct}%`, top: `${s.mapTopPct}%` }}
                  aria-label={`Session ${s.city}`}
                  aria-pressed={sessionId === s.id}
                  onClick={() => setSessionId(s.id)}
                >
                  <span className={`is-${st}`} />
                  <b>{s.city}</b>
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
                  className={sessionId === s.id ? 'active' : undefined}
                  aria-pressed={sessionId === s.id}
                  onClick={() => setSessionId(s.id)}
                >
                  {s.region}
                  <small className={`session-status is-${st}`}>{sessionStatusLabel(st)}</small>
                </button>
              )
            })}
          </div>
          <div className="session-detail" id="desk-session-detail">
            <strong>
              {selectedSession.city}{' '}
              <span className={`session-status is-${sessionStatus(selectedSession, now)}`}>
                {sessionStatusLabel(sessionStatus(selectedSession, now))}
              </span>
            </strong>
            <span className="mono">{formatSessionHoursLocal(selectedSession, now)}</span>
          </div>
          <p className="map-foot muted">
            Crypto <b>24/7</b> · sessions FX fermées le week-end
          </p>
        </CardShell>

        <CardShell
          title="Marchés principaux"
          footer={
            <Link to="/app/market" className="link">
              Tout le marché ↗
            </Link>
          }
        >
          {loading && !primaryMarkets.length ? (
            <p className="muted">Chargement…</p>
          ) : !primaryMarkets.length ? (
            <p className="muted">Aucun ticker screener.</p>
          ) : (
            <div className="desk-tickers">
              {primaryMarkets.map((r) => (
                <Link
                  key={r.symbol}
                  className="desk-ticker"
                  to={`/app/market?symbol=${encodeURIComponent(r.symbol)}`}
                >
                  <span>
                    <b>
                      {r.symbol.replace(/USDT$/i, '')}
                      <small className="desk-quote"> / USDT</small>
                    </b>
                    <small>
                      <VerdictBadge decision={r.decision} pipeline={r.pipeline} hideDiagnostic />
                    </small>
                  </span>
                  <span className="right">
                    <b className="mono">{fmtPrice(r.price)}</b>
                    {(() => {
                      const chg = changeBySymbol[r.symbol.toUpperCase()]
                      if (chg == null || Number.isNaN(chg)) {
                        return (
                          <small className="muted">
                            {r.rvol != null
                              ? `RVOL ${fmtDec(r.rvol, 2)}×`
                              : `conf ${fmtPct(r.confidence, 0, false)}`}
                          </small>
                        )
                      }
                      const tone = chg > 0 ? 'is-up' : chg < 0 ? 'is-down' : ''
                      return (
                        <small className={`mono desk-chg ${tone}`.trim()}>
                          {fmtPctPoints(chg, 2, true)}
                        </small>
                      )
                    })()}
                  </span>
                </Link>
              ))}
            </div>
          )}
        </CardShell>

        <CardShell title="Lecture du marché">
          {climateError && !market ? (
            <p className="muted">{climateError}</p>
          ) : loading && !market && !fng ? (
            <p className="muted">Chargement…</p>
          ) : !market && !fng ? (
            <p className="muted">Climat crypto indisponible.</p>
          ) : (
            <div className="desk-climate">
              {fng ? (
                <div className="climate-head">
                  <span className="climate-symbol" aria-hidden>
                    {fng.value >= 55 ? '↗' : fng.value <= 45 ? '↘' : '→'}
                  </span>
                  <div>
                    <small>SENTIMENT (FEAR &amp; GREED)</small>
                    <h3>{fng.classification}</h3>
                  </div>
                </div>
              ) : null}
              {market ? (
                <dl className="desk-climate-stats">
                  <div>
                    <dt>Capitalisation crypto 24h</dt>
                    <dd className={market.marketCapChangePercent24h >= 0 ? 'up' : 'down'}>
                      {fmtPctPoints(market.marketCapChangePercent24h, 2, true)}
                    </dd>
                  </div>
                  {(() => {
                    const btc = market.dominance.find((d) => d.symbol.toUpperCase() === 'BTC')
                    if (!btc) return null
                    return (
                      <div>
                        <dt>Dominance BTC</dt>
                        <dd className="mono">{fmtPctPoints(btc.percent, 1, false)}</dd>
                      </div>
                    )
                  })()}
                </dl>
              ) : null}
              <Link to="/app/context" className="link">
                Ouvrir le contexte ↗
              </Link>
            </div>
          )}
        </CardShell>
      </div>

      {/* 5. Trajectoire */}
      <CardShell title="Trajectoire du portefeuille" meta={BASELINE}>
        {ovError ? (
          <p className="muted">{ovError}</p>
        ) : (
          <EquityChart
            points={overview?.equity_curve ?? []}
            initial={acct?.initial_cash ?? 0}
            period={equityPeriod}
            onPeriod={setEquityPeriod}
          />
        )}
      </CardShell>

      <div className="desk-grid-2">
        {/* 6. À surveiller */}
        <CardShell
          title="À surveiller"
          footer={
            <Link to="/app/opportunites" className="link">
              Toutes les opportunités ↗
            </Link>
          }
        >
          {loading && !watchList.length ? (
            <p className="muted">Chargement…</p>
          ) : !watchList.length ? (
            <p className="muted">Aucune opportunité actionnable (BUY/SELL).</p>
          ) : (
            <ul className="desk-watch-list">
              {watchList.map((r) => (
                <li key={r.symbol}>
                  <Link to={`/app/opportunites?symbol=${encodeURIComponent(r.symbol)}`}>
                    <strong>{r.symbol.replace(/USDT$/i, '')}</strong>
                    <VerdictBadge decision={r.decision} pipeline={r.pipeline} hideDiagnostic />
                    <span className="mono muted">{fmtPct(r.confidence, 0, false)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </CardShell>

        {/* 7. Notice fraîcheur — only if issues */}
        {freshnessIssues.length > 0 ? (
          <div className="banner desk-freshness" role="status">
            <strong>Fraîcheur données</strong>
            <span>
              {' '}
              {freshnessIssues.slice(0, 6).join(', ')}
              {freshnessIssues.length > 6 ? ` (+${freshnessIssues.length - 6})` : ''} — données
              stale / tardives ou mark position périmé.
            </span>
            <Link to="/app/operations" className="link">
              Voir Opérations ↗
            </Link>
          </div>
        ) : null}

        {/* 8. Positions */}
        <CardShell
          title="Positions ouvertes"
          meta={acct ? `${acct.open_positions} ouvertes` : undefined}
          footer={
            <Link to="/app/portefeuille?tab=positions" className="link">
              Portefeuille ↗
            </Link>
          }
        >
          {ovError ? (
            <p className="muted">{ovError}</p>
          ) : !(overview?.positions.length) ? (
            <p className="muted">Aucune position ouverte.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Actif</th>
                    <th>Engagé</th>
                    <th>P&amp;L latent</th>
                    <th>État</th>
                  </tr>
                </thead>
                <tbody>
                  {(overview?.positions ?? []).slice(0, 8).map((p: PaperOverviewPosition) => (
                    <tr key={p.id ?? p.symbol}>
                      <td>
                        <b>{p.symbol.replace(/USDT$/i, '')}</b>
                        <small className="muted"> {p.direction}</small>
                      </td>
                      <td className="mono">
                        {fmtEur(
                          p.market_value ??
                            (p.current_price != null && p.qty != null
                              ? p.current_price * Math.abs(p.qty)
                              : null),
                          0,
                        )}
                      </td>
                      <td
                        className={`mono ${
                          (p.unrealized_pnl ?? 0) > 0
                            ? 'up'
                            : (p.unrealized_pnl ?? 0) < 0
                              ? 'down'
                              : ''
                        }`}
                      >
                        {fmtEur(p.unrealized_pnl, 0)}
                      </td>
                      <td>{p.mark_stale ? 'Mark stale' : 'Ouverte'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardShell>

        {/* 9. Budget risque */}
        <CardShell title="Votre budget de risque">
          {!risk ? (
            <p className="muted">{ovError ?? (loading ? 'Chargement…' : 'Risque indisponible.')}</p>
          ) : (
            <div className="desk-risk-bars">
              <div>
                <div className="desk-risk-label">
                  <span>Exposition / limite</span>
                  <span className="mono">
                    {risk.open_risk_pct != null ? fmtPct(risk.open_risk_pct, 1, false) : '—'}
                    {risk.max_open_risk_pct != null
                      ? ` / ${fmtPct(risk.max_open_risk_pct, 0, false)}`
                      : ''}
                  </span>
                </div>
                <div className="desk-risk-track" aria-hidden>
                  <i
                    style={{
                      width: `${Math.min(
                        100,
                        risk.max_open_risk_pct && risk.open_risk_pct != null
                          ? (risk.open_risk_pct / risk.max_open_risk_pct) * 100
                          : 0,
                      )}%`,
                    }}
                  />
                </div>
              </div>
              <div>
                <div className="desk-risk-label">
                  <span>Slots positions</span>
                  <span className="mono">
                    {risk.open_positions} / {risk.max_open_positions}
                  </span>
                </div>
                <div className="desk-risk-track" aria-hidden>
                  <i
                    style={{
                      width: `${Math.min(
                        100,
                        risk.max_open_positions
                          ? (risk.open_positions / risk.max_open_positions) * 100
                          : 0,
                      )}%`,
                    }}
                  />
                </div>
              </div>
              <p className="desk-note">
                Perte journalière :{' '}
                <strong>
                  {lock?.daily_loss_locked ? 'verrouillée' : 'ouverte'}
                </strong>
                {lock?.kill_switch_armed ? ' · kill-switch armé' : ''}
              </p>
            </div>
          )}
        </CardShell>
      </div>

      <div className="desk-grid-2">
        {/* 10. Événements */}
        <CardShell
          title="Derniers événements"
          footer={
            <Link to="/app/operations" className="link">
              Historique ↗
            </Link>
          }
        >
          {tapeError ? (
            <p className="muted">{tapeError}</p>
          ) : !tape.length ? (
            <p className="muted">Aucun événement récent.</p>
          ) : (
            <ul className="ov-tape-list">
              {tape.map((it) => (
                <li key={`${it.time}-${it.kind}-${it.symbol}-${it.portfolio}-${it.detail}`}>
                  <span className={`ov-tape-dot ${toneClass(it.tone)}`} aria-hidden />
                  <span className="ov-tape-time mono muted">{fmtClock(it.time)}</span>
                  <div className="ov-tape-body">
                    <strong>{it.title}</strong>
                    <span className="muted">{it.detail}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardShell>

        {/* 11. Prochain contrôle */}
        <CardShell title="Le prochain contrôle">
          <dl className="desk-climate-stats">
            <div>
              <dt>Clôture bougie 1H</dt>
              <dd className="mono">
                {nextClose.toLocaleTimeString(undefined, {
                  hour: '2-digit',
                  minute: '2-digit',
                })}{' '}
                <small className="muted">({formatCountdown(nextClose, now)})</small>
              </dd>
            </div>
            <div>
              <dt>RVOL BTC</dt>
              <dd className="mono">
                {btcRow?.rvol != null ? `${fmtDec(btcRow.rvol, 2)}×` : '—'}
              </dd>
            </div>
          </dl>
          {!btcRow && !loading ? (
            <p className="muted">BTCUSDT absent du screener.</p>
          ) : null}
        </CardShell>

        {/* 12. État système */}
        <CardShell title="État du système">
          <ul className="desk-system-list">
            <li>
              <span>Moteur</span>
              <strong className={engineOk ? 'up' : 'down'}>
                {engineOk == null ? '…' : engineOk ? 'OK' : 'Hors ligne'}
              </strong>
            </li>
            <li>
              <span>Risk Kernel</span>
              <strong>{risk?.kernel ?? '—'}</strong>
            </li>
            <li>
              <span>Kill-switch</span>
              <strong>{lock?.kill_switch_armed ? 'Armé' : 'Désarmé'}</strong>
            </li>
            <li>
              <span>Mode</span>
              <strong>PAPER</strong>
            </li>
            <li>
              <span>Exécution réelle</span>
              <strong>Désactivée</strong>
            </li>
          </ul>
        </CardShell>
      </div>

      {/* 13–14. Anneaux */}
      <div className="desk-allocation">
        <CardShell
          title="Répartition du capital"
          meta={acct ? fmtEur(acct.equity, 0) : undefined}
          footer={
            <Link to="/app/portefeuille" className="link">
              Voir l’allocation ↗
            </Link>
          }
        >
          {!acct ? (
            <p className="muted">{loading ? 'Chargement…' : ovError ?? 'Compte indisponible.'}</p>
          ) : (
            <div className="allocation-body">
              <Ring
                parts={[{ pct: investedPct, color: '#548f87' }]}
                center={fmtPctPoints(investedPct, 1, false)}
                label="Capital engagé"
              />
              <div className="allocation-legend">
                <div className="statline">
                  <span>
                    <i className="legend-dot teal" aria-hidden /> Engagé
                  </span>
                  <b className="mono">{fmtEur(acct.invested, 0)}</b>
                </div>
                <div className="statline">
                  <span>
                    <i className="legend-dot neutral" aria-hidden /> Disponible
                  </span>
                  <b className="mono">{fmtEur(acct.cash, 0)}</b>
                </div>
                <p className="desk-note">
                  {acct.equity > 0
                    ? `${fmtPct(acct.cash / acct.equity, 1, false)} du capital reste disponible.`
                    : null}
                </p>
              </div>
            </div>
          )}
        </CardShell>

        <CardShell
          title="Concentration des positions"
          footer={
            <Link to="/app/portefeuille?tab=positions" className="link">
              Surveiller la concentration ↗
            </Link>
          }
        >
          {!concentration.length ? (
            <p className="muted">
              {loading ? 'Chargement…' : 'Aucune position valorisée pour calculer la concentration.'}
            </p>
          ) : (
            <div className="allocation-body">
              <Ring
                parts={concentration.slice(0, 5).map((c, i) => ({
                  pct: c.pct,
                  color: RING_COLORS[i % RING_COLORS.length],
                }))}
                center={String(concentration.length)}
                label="Positions"
              />
              <div className="allocation-legend">
                {concentration.slice(0, 5).map((c, i) => (
                  <div key={c.symbol} className="statline concentration-row">
                    <span>
                      <i
                        className="legend-dot"
                        style={{ background: RING_COLORS[i % RING_COLORS.length] }}
                        aria-hidden
                      />
                      {c.symbol}
                    </span>
                    <b className="mono">{fmtPctPoints(c.pct, 1, false)}</b>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardShell>
      </div>
    </div>
  )
}
