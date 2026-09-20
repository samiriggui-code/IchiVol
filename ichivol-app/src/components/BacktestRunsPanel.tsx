import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { EXPERIMENT_LABELS, getBacktestRuns, type BacktestRun, type BacktestRuns } from '../lib/activity'
import '../pages/ActivityPage.css'

function fmtDateTime(iso: string): string {
  return new Date(iso).toLocaleString('fr-FR', {
    weekday: 'short',
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function fmtNum(n: number | null, digits = 2): string {
  return n == null ? '—' : n.toFixed(digits)
}

function RunTable({ run, minTrades }: { run: BacktestRun; minTrades: number }) {
  return (
    <div className="table-wrap">
      <table>
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
          {Object.entries(run.experiments).map(([name, e]) => (
            <tr key={name}>
              <td>{EXPERIMENT_LABELS[name] ?? name}</td>
              <td className="mono">
                {e.trades_mean.toFixed(1)}
                {e.small_sample && (
                  <span
                    className="muted"
                    title={`Moins de ${minTrades} trades par paire : trop peu pour conclure`}
                  >
                    {' '}
                    · échantillon faible
                  </span>
                )}
              </td>
              <td className="mono">
                {e.win_rate_mean == null ? '—' : `${(e.win_rate_mean * 100).toFixed(0)} %`}
              </td>
              <td className="mono">{fmtNum(e.profit_factor_median)}</td>
              <td className="mono">{fmtNum(e.sharpe_mean)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Historique des backtests lancés automatiquement, daté, avec le détail par méthode. */
export function BacktestRunsPanel() {
  const [data, setData] = useState<BacktestRuns | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getBacktestRuns(30)
      .then((d) => {
        if (!cancelled) setData(d)
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Historique indisponible')
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <section className="panel" aria-label="Lancements automatiques">
      <header className="panel-head">
        <h2>Lancements automatiques</h2>
        <span className="panel-meta">
          {data ? `${data.total_runs} au total` : '…'} · vue d’ensemble dans <Link to="/app/activite">Activité</Link>
        </span>
      </header>
      {error && <div className="banner error">{error}</div>}
      {data && data.runs.length === 0 && <p className="muted">Aucun lancement enregistré.</p>}
      {data && data.runs.length > 0 && (
        <ul className="act-list" style={{ padding: '0 0.75rem 0.5rem' }}>
          {data.runs.map((run) => {
            const key = run.started_at
            const isOpen = open === key
            const v = run.pipeline_vs_ichimoku
            return (
              <li key={key} style={{ borderTop: '1px solid var(--border)', padding: '0.45rem 0' }}>
                <button
                  type="button"
                  className="act-run-toggle"
                  onClick={() => setOpen(isOpen ? null : key)}
                  aria-expanded={isOpen}
                >
                  <strong>{fmtDateTime(run.ended_at)}</strong>
                  <span className="muted">
                    {' '}
                    — {run.n_pairs} paires, {run.n_rows} résultats · le pipeline bat Ichimoku sur {v.beats}/
                    {v.compared}
                  </span>
                  <span className="act-chevron">{isOpen ? '▾' : '▸'}</span>
                </button>
                {isOpen && <RunTable run={run} minTrades={data.min_trades_per_pair} />}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
