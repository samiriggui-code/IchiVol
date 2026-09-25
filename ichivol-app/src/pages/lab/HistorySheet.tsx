import { BacktestRunsList } from '../../components/BacktestRunsPanel'
import { fmtWhen } from './labShared'
import type { useLabController } from './useLabController'

type Ctrl = ReturnType<typeof useLabController>

export function HistorySheet({ c }: { c: Ctrl }) {
  const { historyOpen, setHistoryOpen, evidence, edgeLabel, edge } = c
  if (!historyOpen) return null
  return (
    <aside className="panel decision-sheet bt-sheet" aria-label="Historique des backtests automatiques">
      <header className="panel-head decision-sheet-head">
        <div>
          <h2>Historique automatique</h2>
          <span className="panel-meta">backtests quotidiens · preuve C1</span>
        </div>
        <button type="button" className="ghost decision-sheet-close" onClick={() => setHistoryOpen(false)}>
          Fermer
        </button>
      </header>
      <div className="decision-sheet-scroll">
        <section className="overview-collect backtests-evidence" aria-label="Collecte automatique">
          <div className="panel overview-stat">
            <span className="overview-stat-label muted">Collecte auto (C1)</span>
            <strong className="mono">
              {evidence?.enabled === false
                ? 'off'
                : evidence
                  ? `${evidence.runs_total ?? evidence.total_rows} ${evidence.runs_total != null ? 'lancements' : 'lignes'}`
                  : '—'}
            </strong>
            <span className="overview-stat-meta muted">
              {evidence?.enabled === false
                ? 'Job désactivé (ENABLE_BACKTEST_EVIDENCE)'
                : evidence?.note
                  ? evidence.note
                  : `Dernier cycle ${fmtWhen(evidence?.last_run_at ?? null)}`}
              {evidence && evidence.distinct_days > 0
                ? ` · ${evidence.distinct_days} j d’historique · ${evidence.total_rows} résultats`
                : ''}
            </span>
          </div>
          <div className="panel overview-stat">
            <span className="overview-stat-label muted">PIPELINE &gt; Ichimoku (Sharpe)</span>
            <strong className="mono">{edgeLabel}</strong>
            <span className="overview-stat-meta muted">
              {edge
                ? `paires du dernier cycle · ${evidence?.latest_pairs ?? 0} paires scorées`
                : 'Indicateur descriptif — ne promeut pas Option C ni le live'}
            </span>
          </div>
        </section>
        <BacktestRunsList />
      </div>
    </aside>
  )
}
