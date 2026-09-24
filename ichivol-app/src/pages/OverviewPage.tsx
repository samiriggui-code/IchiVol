import { useCallback, useEffect, useMemo, useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { ContextPanel } from '../components/ContextPanel'
import { VerdictBadge } from '../components/VerdictBadge'
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
  type PaperPortfolioRow,
} from '../lib/paper'
import { asGate } from '../lib/verdict'
import './OverviewPage.css'

const BASELINE = 'ICHIVOL_BASELINE_V1'
const REFRESH_MS = 60_000
const TAPE_LIMIT = 8

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
  const stagePass: Record<string, number> = {
    direction: 0,
    participation: 0,
    structure: 0,
    location: 0,
    regime: 0,
  }
  for (const r of rows) {
    const bucket = verdictBucket(r)
    if (bucket === 'buy') buy += 1
    else if (bucket === 'sell') sell += 1
    else if (bucket === 'watch') watch += 1
    const stages = r.pipeline?.stages
    if (Array.isArray(stages)) {
      for (const s of stages) {
        if (s.id in stagePass && s.status === 'pass') {
          stagePass[s.id] += 1
        }
      }
    }
  }
  const top = rows
    .filter((r) => {
      const b = verdictBucket(r)
      return b === 'buy' || b === 'sell'
    })
    .sort((a, b) => b.confidence - a.confidence)
    .slice(0, 6)
  const none = Math.max(0, rows.length - buy - sell - watch)
  return { buy, sell, watch, none, top, total: rows.length, stagePass }
}

function fmtPct(v: number | null | undefined, digits = 1): string {
  if (v == null || Number.isNaN(v)) return '—'
  const sign = v > 0 ? '+' : ''
  return `${sign}${(v * 100).toFixed(digits)} %`
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

function fmtInt(n: number): string {
  return n.toLocaleString('fr-FR')
}

function fmtWhen(iso: string | null): string {
  if (!iso) return 'jamais'
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return '—'
  const ageSec = (Date.now() - t) / 1000
  if (ageSec < 3600) return `il y a ${Math.max(1, Math.floor(ageSec / 60))} min`
  if (ageSec < 86400) return `il y a ${Math.floor(ageSec / 3600)} h`
  return `il y a ${Math.floor(ageSec / 86400)} j`
}

function fmtClock(iso: string): string {
  return new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
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

function EquitySpark({ points, initial }: { points: { equity: number }[]; initial: number }) {
  if (points.length < 2) {
    return <div className="ov-spark ov-spark--empty muted">Courbe en construction</div>
  }
  const vals = points.map((p) => p.equity)
  const min = Math.min(...vals, initial)
  const max = Math.max(...vals, initial)
  const span = Math.max(1e-6, max - min)
  const w = 160
  const h = 40
  const poly = vals
    .map((v, i) => {
      const x = (i / (vals.length - 1)) * w
      const y = h - ((v - min) / span) * (h - 4) - 2
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
  const up = vals[vals.length - 1] >= initial
  return (
    <svg className={`ov-spark ${up ? 'is-up' : 'is-down'}`} viewBox={`0 0 ${w} ${h}`} aria-hidden>
      <polyline fill="none" strokeWidth="1.6" points={poly} />
    </svg>
  )
}

function DeskKpi({
  label,
  value,
  meta,
  tone,
}: {
  label: string
  value: string
  meta?: string
  tone?: 'bull' | 'bear' | 'flat'
}) {
  return (
    <div className={`ov-desk-kpi${tone && tone !== 'flat' ? ` is-${tone}` : ''}`}>
      <span className="overview-stat-label muted">{label}</span>
      <strong className="mono">{value}</strong>
      {meta ? <span className="overview-stat-meta muted">{meta}</span> : null}
    </div>
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
  const dayPct =
    acct?.day_change != null && acct.equity
      ? acct.day_change / Math.max(1e-9, acct.equity - acct.day_change)
      : null
  const totalPct =
    acct != null && acct.initial_cash > 0 ? acct.total_pnl / acct.initial_cash : null
  const dayTone: 'bull' | 'bear' | 'flat' =
    acct?.day_change == null ? 'flat' : acct.day_change > 0 ? 'bull' : acct.day_change < 0 ? 'bear' : 'flat'

  const circuitAlive = (summary?.decisions.last_24h ?? 0) > 0
  const edgeHint = evidence?.pipeline_beats_ichimoku_sharpe

  const labs = useMemo(() => {
    return [...portfolios].sort((a, b) => {
      if (a.code === BASELINE) return -1
      if (b.code === BASELINE) return 1
      return b.realized_pnl - a.realized_pnl
    })
  }, [portfolios])

  const openBook = overview?.positions.slice(0, 6) ?? []

  return (
    <div className="overview-page">
      <header className="page-head overview-head iv-animate-soft">
        <div>
          <p className="iv-page-eyebrow">Trading · Desk</p>
          <h1>Desk</h1>
          <p className="iv-page-question">
            Que se passe-t-il maintenant ?
            {circuitAlive
              ? ` · ${fmtInt(summary?.decisions.last_24h ?? 0)} décisions / 24 h`
              : ''}
            {cacheAge != null ? ` · screener ${fmtCacheAge(cacheAge)}` : ''}
          </p>
        </div>
        <div className="market-class-tabs">
          <button type="button" onClick={() => void load(true)} disabled={loading}>
            {loading ? '…' : 'Actualiser'}
          </button>
        </div>
      </header>

      {error && (
        <div className="banner error" role="alert">
          {error}
        </div>
      )}

      <section className="iv-metrics iv-animate-in" aria-label="Synthèse marché">
        <div className="iv-metric">
          <div className="iv-metric-label">Marchés analysés</div>
          <div className="iv-metric-value mono">{loading && !rows.length ? '—' : fmtInt(stats.total)}</div>
          <small>Screener 1h</small>
        </div>
        <div className="iv-metric">
          <div className="iv-metric-label">Opportunités</div>
          <div className={`iv-metric-value mono${stats.buy > 0 ? ' is-bull' : ''}`}>
            {loading && !rows.length ? '—' : fmtInt(stats.buy)}
          </div>
          <small>
            {loading && !rows.length
              ? 'BUY actionnables'
              : `SELL : ${fmtInt(stats.sell)} signaux (short désactivé)`}
          </small>
        </div>
        <div className="iv-metric">
          <div className="iv-metric-label">WATCH</div>
          <div className="iv-metric-value mono">{loading && !rows.length ? '—' : fmtInt(stats.watch)}</div>
          <small>Prudence — pas d’entrée</small>
        </div>
        <div className="iv-metric">
          <div className="iv-metric-label">Positions paper</div>
          <div className="iv-metric-value mono">{acct ? fmtInt(acct.open_positions) : '—'}</div>
          <small>{BASELINE}</small>
        </div>
        <div className="iv-metric">
          <div className="iv-metric-label">
            {overview?.risk ? 'Risque engagé' : 'Exposé'}
          </div>
          <div className="iv-metric-value mono">
            {overview?.risk?.open_risk_pct != null
              ? `${(overview.risk.open_risk_pct * 100).toFixed(1)} %`
              : overview?.risk
                ? fmtEur(overview.risk.open_risk_amount, 0)
                : acct
                  ? fmtEur(acct.invested, 0)
                  : '—'}
          </div>
          <small>
            {overview?.risk
              ? `ouvert ${fmtEur(overview.risk.open_risk_amount, 0)} / exposé ${fmtEur(overview.risk.exposed, 0)}`
              : acct
                ? `capital engagé ${fmtEur(acct.invested, 0)}`
                : '—'}
          </small>
        </div>
      </section>

      <div className="iv-desk-grid iv-animate-in-delay">
        <section className="panel" aria-label="Market pulse">
          <header className="panel-head">
            <h2>Market pulse</h2>
            <span className="muted">Distribution actuelle</span>
          </header>
          <div className="card-body iv-pulse" style={{ padding: '0.75rem 1rem 1.1rem' }}>
            <div
              className="iv-donut"
              style={
                {
                  ['--buy' as string]: stats.total
                    ? ((stats.buy / stats.total) * 100).toFixed(2)
                    : 0,
                  ['--sell' as string]: stats.total
                    ? ((stats.sell / stats.total) * 100).toFixed(2)
                    : 0,
                  ['--watch' as string]: stats.total
                    ? ((stats.watch / stats.total) * 100).toFixed(2)
                    : 0,
                } as CSSProperties
              }
              data-center={loading && !rows.length ? '—' : String(stats.total)}
              role="img"
              aria-label={`${stats.total} marchés : ${stats.buy} buy, ${stats.sell} sell, ${stats.watch} watch, ${stats.none} no trade`}
            />
            <div className="iv-pulse-legend">
              <span>
                <span>
                  <i className="is-buy" aria-hidden />
                  BUY
                </span>
                <b className="mono">{stats.buy}</b>
              </span>
              <span>
                <span>
                  <i className="is-sell" aria-hidden />
                  SELL
                </span>
                <b className="mono">{stats.sell}</b>
              </span>
              <span>
                <span>
                  <i className="is-watch" aria-hidden />
                  WATCH
                </span>
                <b className="mono">{stats.watch}</b>
              </span>
              <span>
                <span>
                  <i className="is-none" aria-hidden />
                  NO TRADE
                </span>
                <b className="mono">{stats.none}</b>
              </span>
            </div>
          </div>
        </section>

        <section className="panel" aria-label="Top opportunités">
          <header className="panel-head">
            <h2>Top opportunités</h2>
            <Link to="/app/opportunites" className="ghost">
              Voir tout →
            </Link>
          </header>
          {stats.top.length === 0 ? (
            <p className="muted overview-empty" style={{ padding: '0.75rem 1rem' }}>
              {loading ? 'Scan screener…' : 'Aucune opportunité actionnable'}
            </p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Symbole</th>
                    <th>Décision</th>
                    <th>Conf.</th>
                    <th>RVOL</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.top.map((r) => (
                    <tr key={r.symbol}>
                      <td>
                        <Link to={`/app/opportunites?symbol=${encodeURIComponent(r.symbol)}`}>
                          <strong>{r.symbol.replace(/USDT$/i, '')}</strong>
                        </Link>
                      </td>
                      <td>
                        <VerdictBadge decision={r.decision} pipeline={r.pipeline} />
                      </td>
                      <td className="mono">{(r.confidence * 100).toFixed(0)}%</td>
                      <td className="mono">{r.rvol != null ? `${r.rvol.toFixed(2)}×` : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      <section className="panel" aria-label="Pipeline health" style={{ marginBottom: '1rem' }}>
        <header className="panel-head">
          <h2>Pipeline health</h2>
          <span className="muted">Marchés ayant passé chaque porte</span>
        </header>
        <ul className="iv-pipeline" style={{ margin: '0 0.75rem 1rem' }}>
          {(
            [
              ['analysés', stats.total],
              ['direction', stats.stagePass.direction],
              ['participation', stats.stagePass.participation],
              ['structure', stats.stagePass.structure],
              ['location', stats.stagePass.location],
              ['régime', stats.stagePass.regime],
              ['opportunités (BUY)', stats.buy],
            ] as const
          ).map(([label, n]) => (
            <li key={label}>
              <strong className="mono">{loading && !rows.length ? '—' : fmtInt(n)}</strong>
              <span>{label}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="panel ov-desk" aria-label="Compte baseline">
        <header className="panel-head">
          <h2>Capital · {BASELINE}</h2>
          <Link to="/app/portefeuille" className="ghost">
            Portefeuille →
          </Link>
        </header>
        <div className="ov-desk-body">
          <div className="ov-desk-hero">
            <DeskKpi
              label="Equity"
              value={acct ? fmtEur(acct.equity, 0) : '—'}
              meta={totalPct != null ? `depuis départ ${fmtPct(totalPct)}` : undefined}
              tone={
                totalPct == null ? 'flat' : totalPct > 0 ? 'bull' : totalPct < 0 ? 'bear' : 'flat'
              }
            />
            <DeskKpi
              label="Jour"
              value={acct?.day_change != null ? fmtEur(acct.day_change, 0) : '—'}
              meta={dayPct != null ? fmtPct(dayPct) : undefined}
              tone={dayTone}
            />
            <DeskKpi
              label="Cash / engagé"
              value={acct ? `${fmtEur(acct.cash, 0)} / ${fmtEur(acct.invested, 0)}` : '—'}
              meta={acct ? `${acct.open_positions} ouvertes` : undefined}
            />
            <DeskKpi
              label="P&L latent"
              value={acct ? fmtEur(acct.unrealized_pnl, 0) : '—'}
              meta={acct ? `réalisé ${fmtEur(acct.realized_pnl, 0)}` : undefined}
              tone={
                acct == null
                  ? 'flat'
                  : acct.unrealized_pnl > 0
                    ? 'bull'
                    : acct.unrealized_pnl < 0
                      ? 'bear'
                      : 'flat'
              }
            />
          </div>
          <EquitySpark points={overview?.equity_curve ?? []} initial={acct?.initial_cash ?? 5000} />
        </div>
      </section>

      <section className="ov-circuit" aria-label="Circuit 24 h">
        <article className={`panel overview-stat ov-pulse ${circuitAlive ? 'is-ok' : 'is-warn'}`}>
          <span className="overview-stat-label muted">Décisions 24 h</span>
          <strong className="mono">{summary ? fmtInt(summary.decisions.last_24h) : '—'}</strong>
          <span className="overview-stat-meta muted">
            {summary ? `${fmtInt(summary.decisions.total)} total · ${fmtWhen(summary.decisions.last_at)}` : '…'}
          </span>
          <Link to="/app/operations" className="overview-stat-link">
            Opérations →
          </Link>
        </article>
        <article className="panel overview-stat ov-pulse is-ok">
          <span className="overview-stat-label muted">Paper 24 h</span>
          <strong className="mono">
            {summary
              ? `${fmtInt(summary.paper.opened_24h)} / ${fmtInt(summary.paper.closed_24h)}`
              : '—'}
          </strong>
          <span className="overview-stat-meta muted">
            {summary
              ? `ouv. / clôt. · ${summary.paper.open_now} en cours`
              : '…'}
          </span>
        </article>
        <article className="panel overview-stat ov-pulse">
          <span className="overview-stat-label muted">Strategy Lab</span>
          <strong className="mono">{summary ? fmtInt(summary.backtest.runs_total) : '—'}</strong>
          <span className="overview-stat-meta muted">
            {summary ? `dernier ${fmtWhen(summary.backtest.last_at)}` : '…'}
          </span>
        </article>
      </section>

      <div className="ov-main">
        <section className="panel ov-book" aria-label="Livre live">
          <header className="panel-head">
            <h2>Livre live · 1h</h2>
            <Link to="/app/opportunites" className="ghost">
              Opportunités →
            </Link>
          </header>
          <div className="ov-book-stats">
            <div className="panel overview-stat overview-stat--bull">
              <span className="overview-stat-label muted">Achats</span>
              <strong className="mono">{loading && !rows.length ? '—' : stats.buy}</strong>
            </div>
            <div className="panel overview-stat overview-stat--bear">
              <span className="overview-stat-label muted">Ventes</span>
              <strong className="mono">{loading && !rows.length ? '—' : stats.sell}</strong>
            </div>
            <div className="panel overview-stat">
              <span className="overview-stat-label muted">Watch</span>
              <strong className="mono">{loading && !rows.length ? '—' : stats.watch}</strong>
            </div>
            <div className="panel overview-stat">
              <span className="overview-stat-label muted">Scannées</span>
              <strong className="mono">{loading && !rows.length ? '—' : stats.total}</strong>
            </div>
          </div>
          {stats.top.length === 0 ? (
            <p className="muted overview-empty">
              {loading ? 'Scan screener…' : 'Aucune ligne — vérifie le moteur.'}
            </p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Symbole</th>
                    <th>Porte</th>
                    <th>Conf.</th>
                    <th>RVOL</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.top.map((r) => (
                    <tr key={r.symbol}>
                      <td>
                        <Link to={`/app/opportunites?symbol=${encodeURIComponent(r.symbol)}`}>
                          <strong>{r.symbol.replace(/USDT$/i, '')}</strong>
                        </Link>
                      </td>
                      <td>
                        <VerdictBadge decision={r.decision} pipeline={r.pipeline} />
                      </td>
                      <td className="mono">{(r.confidence * 100).toFixed(0)}%</td>
                      <td className="mono">{r.rvol != null ? `${r.rvol.toFixed(2)}×` : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* T14a — preuves / filtres / signaux suivis : détail dans Opérations (plus sur le Desk). */}
        <section className="panel ov-proof" aria-label="Preuves">
          <header className="panel-head">
            <h2>Preuves & opérations</h2>
            <Link to="/app/operations" className="ghost">
              Opérations →
            </Link>
          </header>
          <div className="ov-proof-body">
            <p className="muted ov-proof-note">
              Filtres shadow, signaux suivis et journal d’audit vivent dans{' '}
              <Link to="/app/operations">Opérations</Link>. Edge backtest :{' '}
              <Link to="/app/strategy-lab">Strategy Lab</Link>
              {edgeHint
                ? ` · pipeline bat Ichimoku sur ${edgeHint.beats}/${edgeHint.compared} paires`
                : ''}
              .
            </p>
          </div>
        </section>
      </div>

      {openBook.length > 0 && (
        <section className="panel ov-positions" aria-label="Positions ouvertes">
          <header className="panel-head">
            <h2>Livre ouvert</h2>
            <span className="panel-meta">{acct?.open_positions ?? openBook.length} positions</span>
          </header>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Symbole</th>
                  <th>Sens</th>
                  <th>Notional</th>
                  <th>Latent</th>
                </tr>
              </thead>
              <tbody>
                {openBook.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <strong>{p.symbol.replace(/USDT$/i, '')}</strong>
                      <span className="muted"> · {p.timeframe}</span>
                    </td>
                    <td className="mono">{p.direction}</td>
                    <td className="mono">{fmtEur(p.notional ?? null, 0)}</td>
                    <td
                      className={`mono ${
                        (p.unrealized_pnl ?? 0) > 0 ? 'up' : (p.unrealized_pnl ?? 0) < 0 ? 'down' : ''
                      }`}
                    >
                      {p.unrealized_pnl != null ? fmtEur(p.unrealized_pnl, 0) : '—'}
                      {p.unrealized_pct != null ? (
                        <span className="muted"> {fmtPct(p.unrealized_pct)}</span>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <div className="ov-bottom">
        <section className="panel ov-tape" aria-label="Derniers événements">
          <header className="panel-head">
            <h2>Tape</h2>
            <Link to="/app/operations" className="ghost">
              Historique →
            </Link>
          </header>
          {tape.length === 0 ? (
            <p className="muted overview-empty">Aucun événement récent.</p>
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
        </section>

        <section className="panel ov-labs" aria-label="Laboratoires paper">
          <header className="panel-head">
            <h2>Labs paper</h2>
            <Link to="/app/portefeuille?tab=positions" className="ghost">
              Portefeuille →
            </Link>
          </header>
          {labs.length === 0 ? (
            <p className="muted overview-empty">Aucun portefeuille actif.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Code</th>
                    <th>Cash</th>
                    <th>Réalisé</th>
                  </tr>
                </thead>
                <tbody>
                  {labs.slice(0, 8).map((p) => (
                    <tr key={p.code} className={p.code === BASELINE ? 'is-baseline' : undefined}>
                      <td>
                        <strong className="mono">{p.code.replace(/^ICHIVOL_/, '')}</strong>
                        <span className="muted ov-lab-label"> {p.label}</span>
                      </td>
                      <td className="mono">{fmtEur(p.cash, 0)}</td>
                      <td className={`mono ${p.realized_pnl > 0 ? 'up' : p.realized_pnl < 0 ? 'down' : ''}`}>
                        {fmtEur(p.realized_pnl, 0)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      <ContextPanel variant="compact" />
    </div>
  )
}
