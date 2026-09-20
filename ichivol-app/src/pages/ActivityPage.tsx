import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  EXPERIMENT_LABELS,
  getActivityFeed,
  getActivitySummary,
  getBacktestRuns,
  type ActivityItem,
  type ActivitySummary,
  type BacktestRun,
  type BacktestRuns,
} from '../lib/activity'
import { getShadowStats, type ShadowStats } from '../lib/paper'
import './ActivityPage.css'

type Filter = 'all' | 'paper' | 'shadow' | 'backtest'

const FILTERS: { id: Filter; label: string }[] = [
  { id: 'all', label: 'Tout' },
  { id: 'paper', label: 'Trades papier' },
  { id: 'shadow', label: 'Filtres' },
  { id: 'backtest', label: 'Backtests' },
]

const REFRESH_MS = 60_000

type TimelineEntry =
  | { type: 'feed'; time: string; item: ActivityItem; portfolios: string[] }
  | { type: 'run'; time: string; run: BacktestRun }

function fmtWhen(iso: string | null): string {
  if (!iso) return 'jamais'
  return new Date(iso).toLocaleString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function fmtAgo(iso: string | null): string {
  if (!iso) return 'jamais'
  const min = Math.round((Date.now() - new Date(iso).getTime()) / 60_000)
  if (min < 1) return "à l'instant"
  if (min < 60) return `il y a ${min} min`
  if (min < 48 * 60) return `il y a ${Math.round(min / 60)} h`
  return `il y a ${Math.round(min / 1440)} j`
}

function dayLabel(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' })
}

function fmtInt(n: number): string {
  return n.toLocaleString('fr-FR')
}

function fmtNumber(n: number | null, digits = 2): string {
  return n == null ? '—' : n.toFixed(digits)
}

function CircuitCard(props: {
  step: number
  title: string
  what: string
  value: string
  sub: string
  state: 'ok' | 'warn' | 'off'
}) {
  return (
    <article className={`act-step is-${props.state}`}>
      <span className="act-step-num">{props.step}</span>
      <h3>{props.title}</h3>
      <p className="act-step-what">{props.what}</p>
      <strong className="act-step-value">{props.value}</strong>
      <span className="act-step-sub">{props.sub}</span>
    </article>
  )
}

function RunDetail({ run, minTrades }: { run: BacktestRun; minTrades: number }) {
  const names = Object.keys(run.experiments)
  return (
    <div className="act-run-table-wrap">
      <table className="act-run-table">
        <thead>
          <tr>
            <th>Méthode</th>
            <th>Trades / paire</th>
            <th>Réussite</th>
            <th>Profit factor (médiane)</th>
            <th>Sharpe moyen</th>
          </tr>
        </thead>
        <tbody>
          {names.map((name) => {
            const e = run.experiments[name]
            return (
              <tr key={name}>
                <td>{EXPERIMENT_LABELS[name] ?? name}</td>
                <td>
                  {e.trades_mean.toFixed(1)}
                  {e.small_sample && (
                    <span className="act-badge is-warn" title={`Moins de ${minTrades} trades par paire : trop peu pour conclure`}>
                      échantillon faible
                    </span>
                  )}
                </td>
                <td>{e.win_rate_mean == null ? '—' : `${(e.win_rate_mean * 100).toFixed(0)} %`}</td>
                <td>{fmtNumber(e.profit_factor_median)}</td>
                <td>{fmtNumber(e.sharpe_mean)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export function ActivityPage() {
  const [summary, setSummary] = useState<ActivitySummary | null>(null)
  const [feed, setFeed] = useState<ActivityItem[]>([])
  const [runs, setRuns] = useState<BacktestRuns | null>(null)
  const [shadow, setShadow] = useState<ShadowStats | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<Filter>('all')
  const [openRun, setOpenRun] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const [s, f, r, sh] = await Promise.all([
        getActivitySummary(),
        getActivityFeed(150),
        getBacktestRuns(30),
        getShadowStats().catch(() => null),
      ])
      setSummary(s)
      setFeed(f.items)
      setRuns(r)
      setShadow(sh)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Activité indisponible')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
    const id = window.setInterval(() => void load(), REFRESH_MS)
    return () => window.clearInterval(id)
  }, [load])

  const timeline = useMemo(() => {
    const entries: TimelineEntry[] = []
    if (filter !== 'backtest') {
      // Plusieurs portefeuilles suivent le même signal : même minute, même événement,
      // même texte. On les regroupe en une ligne avec la liste des portefeuilles.
      const merged = new Map<string, Extract<TimelineEntry, { type: 'feed' }>>()
      for (const item of feed) {
        const isPaper = item.kind === 'paper_opened' || item.kind === 'paper_closed'
        if (filter === 'paper' && !isPaper) continue
        if (filter === 'shadow' && isPaper) continue
        const key = `${item.time.slice(0, 16)}|${item.kind}|${item.symbol}|${item.detail}`
        const existing = merged.get(key)
        if (existing) existing.portfolios.push(item.portfolio)
        else merged.set(key, { type: 'feed', time: item.time, item, portfolios: [item.portfolio] })
      }
      entries.push(...merged.values())
    }
    if ((filter === 'all' || filter === 'backtest') && runs) {
      for (const run of runs.runs) entries.push({ type: 'run', time: run.ended_at, run })
    }
    entries.sort((a, b) => b.time.localeCompare(a.time))
    const groups: { day: string; entries: TimelineEntry[] }[] = []
    for (const entry of entries) {
      const day = dayLabel(entry.time)
      const last = groups[groups.length - 1]
      if (last && last.day === day) last.entries.push(entry)
      else groups.push({ day, entries: [entry] })
    }
    return groups
  }, [feed, runs, filter])

  const evidenceWired = (summary?.evidence.rows_total ?? 0) > 0
  const minTrades = runs?.min_trades_per_pair ?? 30

  return (
    <div className="page act-page">
      <header className="page-head">
        <div>
          <h1>Activité automatique</h1>
          <p className="muted">
            Tout ce que le système fait sans toi : il lit le marché, ouvre et ferme des trades
            fictifs, refuse certains trades, puis se teste chaque jour. Chaque ligne est datée.
          </p>
        </div>
        <button type="button" className="ghost" onClick={() => void load()} disabled={loading}>
          {loading ? '…' : 'Actualiser'}
        </button>
      </header>

      {error && <div className="banner error">{error}</div>}

      <section className="act-circuit" aria-label="Le circuit automatique">
        <CircuitCard
          step={1}
          title="Décisions"
          what="Le moteur relit régulièrement les marchés surveillés (crypto, forex, métaux, indices) et note chaque décision."
          value={summary ? fmtInt(summary.decisions.total) : '…'}
          sub={summary ? `${fmtInt(summary.decisions.last_24h)} sur 24 h · dernière ${fmtAgo(summary.decisions.last_at)}` : ''}
          state={summary && summary.decisions.last_24h > 0 ? 'ok' : 'warn'}
        />
        <CircuitCard
          step={2}
          title="Trades papier"
          what="Quand le pipeline valide un achat ou une vente, un trade fictif s'ouvre tout seul (jamais d'argent réel)."
          value={summary ? `${fmtInt(summary.paper.opened_total)} ouverts` : '…'}
          sub={
            summary
              ? `${summary.paper.open_now} en cours · dernière ouverture ${fmtAgo(summary.paper.last_opened_at)}`
              : ''
          }
          state={summary && summary.paper.opened_total > 0 ? 'ok' : 'warn'}
        />
        <CircuitCard
          step={3}
          title="Trades refusés"
          what="Des filtres (structure, contexte, Fibonacci) refusent des trades. Le système suit ce qu'ils seraient devenus."
          value={summary ? `${fmtInt(summary.shadow.blocked_total)} refusés` : '…'}
          sub={summary ? `${fmtInt(summary.shadow.judged_total)} jugés a posteriori` : ''}
          state={summary && summary.shadow.blocked_total > 0 ? 'ok' : 'warn'}
        />
        <CircuitCard
          step={4}
          title="Backtests"
          what="Une fois par jour, 5 méthodes sont rejouées sur 20 cryptos (1 h et 4 h) pour comparer le pipeline à Ichimoku seul. Le forex et les métaux ne sont pas couverts."
          value={summary ? `${fmtInt(summary.backtest.runs_total)} lancements` : '…'}
          sub={summary ? `dernier ${fmtAgo(summary.backtest.last_at)}` : ''}
          state={summary && summary.backtest.runs_total > 0 ? 'ok' : 'warn'}
        />
        <CircuitCard
          step={5}
          title="Suivi de chaque signal"
          what="Chaque signal devrait être enregistré puis comparé à ce qui s'est passé ensuite. C'est ce qui prouverait l'efficacité."
          value={summary ? (evidenceWired ? `${fmtInt(summary.evidence.rows_total)} suivis` : 'Non branché') : '…'}
          sub={
            summary && !evidenceWired
              ? "aucun signal enregistré : ce maillon ne se déclenche pas tout seul pour l'instant"
              : ''
          }
          state={evidenceWired ? 'ok' : 'off'}
        />
      </section>

      <section className="panel act-eff" aria-label="Efficacité">
        <header className="panel-head">
          <h2>Ce que ça prouve (pour l&apos;instant)</h2>
        </header>
        <div className="act-eff-body">
          <div>
            <h3>Filtres : ont-ils aidé ?</h3>
            {shadow && shadow.n_closed > 0 ? (
              <>
                <ul className="act-eff-list">
                  {Object.entries(shadow.by_block_source).map(([source, s]) => {
                    const helped = s.mean_pnl_r < 0
                    return (
                      <li key={source}>
                        <strong>{source}</strong> : {s.n} trades refusés, résultat moyen{' '}
                        <span className={helped ? 'act-good' : 'act-bad'}>
                          {s.mean_pnl_r >= 0 ? '+' : ''}
                          {s.mean_pnl_r.toFixed(2)} R
                        </span>{' '}
                        — {helped ? 'le filtre a écarté des perdants (utile)' : 'le filtre a écarté des gagnants (coûteux)'}
                      </li>
                    )
                  })}
                </ul>
                <p className="muted">
                  Verdict du moteur : <strong>{shadow.filter_verdict ?? 'inconnu'}</strong>. Trop peu de trades pour
                  trancher.
                </p>
              </>
            ) : (
              <p className="muted">Pas encore de trade refusé jugé.</p>
            )}
          </div>
          <div>
            <h3>Backtests : le pipeline est-il meilleur ?</h3>
            {runs && runs.runs[0] ? (
              <>
                <p>
                  Au dernier lancement, le pipeline bat Ichimoku seul sur{' '}
                  <strong>
                    {runs.runs[0].pipeline_vs_ichimoku.beats} paires sur {runs.runs[0].pipeline_vs_ichimoku.compared}
                  </strong>{' '}
                  (Sharpe).
                </p>
                <p className="muted">
                  Attention : le pipeline ne fait qu&apos;environ{' '}
                  {runs.runs[0].experiments.PIPELINE?.trades_mean.toFixed(0) ?? '?'} trades par paire (il en faudrait au
                  moins {minTrades}). Son profit factor élevé est du bruit, pas une preuve.
                </p>
              </>
            ) : (
              <p className="muted">Aucun backtest enregistré.</p>
            )}
          </div>
        </div>
      </section>

      <section className="panel act-history" aria-label="Historique">
        <header className="panel-head">
          <h2>Historique</h2>
          <div className="act-filters" role="tablist">
            {FILTERS.map((f) => (
              <button
                key={f.id}
                type="button"
                role="tab"
                aria-selected={filter === f.id}
                className={filter === f.id ? 'is-active' : undefined}
                onClick={() => setFilter(f.id)}
              >
                {f.label}
              </button>
            ))}
          </div>
        </header>

        {!loading && timeline.length === 0 && <p className="muted act-empty">Aucune activité pour ce filtre.</p>}

        {timeline.map((group) => (
          <div key={group.day} className="act-day">
            <h3 className="act-day-title">{group.day}</h3>
            <ul className="act-list">
              {group.entries.map((entry) => {
                if (entry.type === 'run') {
                  const key = entry.run.started_at
                  const open = openRun === key
                  const v = entry.run.pipeline_vs_ichimoku
                  return (
                    <li key={`run-${key}`} className="act-row is-run">
                      <span className="act-time">{fmtWhen(entry.run.ended_at).slice(-5)}</span>
                      <span className="act-dot is-run" aria-hidden />
                      <div className="act-body">
                        <button type="button" className="act-run-toggle" onClick={() => setOpenRun(open ? null : key)}>
                          <strong>Backtest automatique</strong> — {entry.run.n_pairs} paires, {fmtInt(entry.run.n_rows)}{' '}
                          résultats · pipeline &gt; Ichimoku sur {v.beats}/{v.compared}
                          <span className="act-chevron">{open ? '▾' : '▸'}</span>
                        </button>
                        {open && <RunDetail run={entry.run} minTrades={minTrades} />}
                      </div>
                    </li>
                  )
                }
                const it = entry.item
                return (
                  <li key={`${it.time}-${it.kind}-${it.symbol}-${it.portfolio}-${it.detail}`} className="act-row">
                    <span className="act-time">{fmtWhen(it.time).slice(-5)}</span>
                    <span className={`act-dot is-${it.tone}`} aria-hidden />
                    <div className="act-body">
                      <strong>{it.title}</strong>
                      <span className="act-detail">{it.detail}</span>
                    </div>
                    <span
                      className="act-portfolio"
                      title={entry.portfolios.join(', ')}
                    >
                      {entry.portfolios.length > 1 ? `${entry.portfolios.length} portefeuilles` : it.portfolio}
                    </span>
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
      </section>
    </div>
  )
}
