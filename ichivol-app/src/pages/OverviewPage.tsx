import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ContextPanel } from '../components/ContextPanel'
import { VerdictBadge } from '../components/VerdictBadge'
import {
  getActivityFeed,
  getActivitySummary,
  getEvidenceOutcomes,
  type ActivityItem,
  type ActivitySummary,
  type EvidenceOutcomes,
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
  getShadowStats,
  listPaperPortfolios,
  type PaperOverview,
  type PaperPortfolioRow,
  type ShadowStats,
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
  for (const r of rows) {
    const bucket = verdictBucket(r)
    if (bucket === 'buy') buy += 1
    else if (bucket === 'sell') sell += 1
    else if (bucket === 'watch') watch += 1
  }
  const top = [...rows].sort((a, b) => b.confidence - a.confidence).slice(0, 6)
  return { buy, sell, watch, top, total: rows.length }
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
  const [shadow, setShadow] = useState<ShadowStats | null>(null)
  const [outcomes, setOutcomes] = useState<EvidenceOutcomes | null>(null)
  const [portfolios, setPortfolios] = useState<PaperPortfolioRow[]>([])

  const load = useCallback(async (force = false) => {
    setLoading(true)
    type ScreenerOk = Awaited<ReturnType<typeof getScreener>>
    const [screenerRes, ovRes, sumRes, feedRes, evRes, shRes, ocRes, pfRes] = await Promise.all([
      getScreener('1h', force)
        .then((r): ScreenerOk | Error => r)
        .catch((err: unknown): ScreenerOk | Error =>
          err instanceof Error ? err : new Error('Screener indisponible'),
        ),
      getPaperOverview(BASELINE).catch(() => null),
      getActivitySummary().catch(() => null),
      getActivityFeed(40).catch(() => ({ items: [] as ActivityItem[] })),
      getBacktestEvidence().catch(() => null),
      getShadowStats().catch(() => null),
      getEvidenceOutcomes().catch(() => null),
      listPaperPortfolios().catch(() => [] as PaperPortfolioRow[]),
    ])

    if (screenerRes instanceof Error) {
      const msg = screenerRes.message
      setError(
        msg.includes('engine_unreachable') || msg.includes('502')
          ? 'Moteur Python injoignable — lance l’engine pour le cockpit.'
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
    setShadow(shRes)
    setOutcomes(ocRes)
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
  const pipelineOutcome = outcomes?.groups.find((g) => g.id === 'pipeline' || g.id.includes('pipeline'))
  const h10 = pipelineOutcome?.horizons['10']

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
      <header className="page-head overview-head">
        <div>
          <h1>Cockpit</h1>
          <p className="muted">
            {circuitAlive
              ? `Circuit actif · ${fmtInt(summary?.decisions.last_24h ?? 0)} décisions / 24 h`
              : 'Desk paper · décisions live · preuves automatiques'}
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

      <section className="panel ov-desk" aria-label="Compte baseline">
        <header className="panel-head">
          <h2>Desk · {BASELINE}</h2>
          <Link to="/app/synthese" className="ghost">
            Synthèse →
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
          <Link to="/app/activite" className="overview-stat-link">
            Activité →
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
          <span className="overview-stat-label muted">Filtres 24 h</span>
          <strong className="mono">{summary ? fmtInt(summary.shadow.blocked_24h) : '—'}</strong>
          <span className="overview-stat-meta muted">
            {summary ? `${fmtInt(summary.shadow.judged_total)} jugés` : '…'}
          </span>
        </article>
        <article className="panel overview-stat ov-pulse">
          <span className="overview-stat-label muted">Backtests</span>
          <strong className="mono">{summary ? fmtInt(summary.backtest.runs_total) : '—'}</strong>
          <span className="overview-stat-meta muted">
            {summary ? `dernier ${fmtWhen(summary.backtest.last_at)}` : '…'}
          </span>
        </article>
        <article
          className={`panel overview-stat ov-pulse ${
            summary?.evidence.tracking_enabled && summary.evidence.rows_total > 0
              ? 'is-ok'
              : summary?.evidence.tracking_enabled
                ? 'is-warn'
                : 'is-off'
          }`}
        >
          <span className="overview-stat-label muted">Signaux suivis</span>
          <strong className="mono">
            {!summary
              ? '—'
              : !summary.evidence.tracking_enabled
                ? 'Off'
                : summary.evidence.rows_total > 0
                  ? fmtInt(summary.evidence.rows_total)
                  : 'Attente'}
          </strong>
          <span className="overview-stat-meta muted">
            {summary?.evidence.tracking_enabled
              ? `${fmtInt(summary.evidence.measured)} mesurés · ${fmtInt(summary.evidence.complete)} terminés`
              : 'tracking coupé'}
          </span>
        </article>
      </section>

      <div className="ov-main">
        <section className="panel ov-book" aria-label="Livre live">
          <header className="panel-head">
            <h2>Livre live · 1h</h2>
            <Link to="/app/decisions" className="ghost">
              Décisions →
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
                        <Link to={`/app/decisions?symbol=${encodeURIComponent(r.symbol)}`}>
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

        <section className="panel ov-proof" aria-label="Preuves">
          <header className="panel-head">
            <h2>Ce que ça prouve</h2>
            <Link to="/app/activite" className="ghost">
              Détail →
            </Link>
          </header>
          <div className="ov-proof-body">
            <div className="ov-proof-block">
              <h3 className="subhead">Edge backtest</h3>
              <p className="ov-proof-lead">
                {edgeHint ? (
                  <>
                    Pipeline bat Ichimoku sur{' '}
                    <strong className="mono">
                      {edgeHint.beats}/{edgeHint.compared}
                    </strong>{' '}
                    paires (Sharpe).
                  </>
                ) : evidence?.enabled === false ? (
                  'Collecte backtest désactivée.'
                ) : (
                  'Pas encore assez de runs pour conclure.'
                )}
              </p>
              <p className="muted ov-proof-note">
                {evidence?.note
                  ? evidence.note
                  : `Dernier run ${fmtWhen(evidence?.last_run_at ?? null)}`}
                {evidence && evidence.distinct_days > 0
                  ? ` · ${evidence.distinct_days} j d’historique`
                  : ''}
              </p>
              <Link to="/app/backtests" className="overview-stat-link">
                Backtests →
              </Link>
            </div>

            <div className="ov-proof-block">
              <h3 className="subhead">Filtres (shadow)</h3>
              {shadow && shadow.n_closed > 0 ? (
                <>
                  <p className="ov-proof-lead">
                    Verdict : <strong>{shadow.filter_verdict ?? 'inconnu'}</strong>
                    {shadow.mean_pnl_r != null ? (
                      <>
                        {' '}
                        · mean{' '}
                        <span className={shadow.mean_pnl_r < 0 ? 'up' : 'down'}>
                          {shadow.mean_pnl_r >= 0 ? '+' : ''}
                          {shadow.mean_pnl_r.toFixed(2)} R
                        </span>
                      </>
                    ) : null}
                  </p>
                  <p className="muted ov-proof-note">
                    {shadow.n_closed} refusés jugés
                    {shadow.n_closed < 5 ? ' · échantillon encore mince' : ''}
                  </p>
                </>
              ) : (
                <p className="muted">Pas encore de trade refusé jugé.</p>
              )}
            </div>

            <div className="ov-proof-block">
              <h3 className="subhead">Signaux suivis</h3>
              {h10 && h10.n > 0 ? (
                <>
                  <p className="ov-proof-lead">
                    Pipeline @ 10 bougies : hit{' '}
                    <strong className="mono">
                      {h10.hit_rate != null ? `${(h10.hit_rate * 100).toFixed(0)} %` : '—'}
                    </strong>{' '}
                    · n={h10.n}
                    {h10.small_sample ? ' · faible' : ''}
                  </p>
                  <p className="muted ov-proof-note">
                    {outcomes ? `${outcomes.n_used} signaux utilisés / ${outcomes.n_total}` : ''}
                  </p>
                </>
              ) : (
                <p className="muted">
                  {summary?.evidence.tracking_enabled
                    ? 'En attente des premiers outcomes mesurés.'
                    : 'Suivi désactivé (ENABLE_SIGNAL_TRACKING).'}
                </p>
              )}
            </div>
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
            <Link to="/app/activite" className="ghost">
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
            <Link to="/app/paper" className="ghost">
              Paper →
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
