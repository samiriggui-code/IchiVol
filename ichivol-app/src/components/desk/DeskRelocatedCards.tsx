import { type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import type { ActivitySummary } from '../../lib/activity'
import type { BacktestEvidenceSummary } from '../../lib/backtest'
import type { ScreenerDecisionRow } from '../../lib/decisions'
import type { PaperPortfolioRow } from '../../lib/paper'
import { summarizeScreener } from '../../lib/deskSummarize'
import './DeskRelocatedCards.css'

const BASELINE = 'ICHIVOL_BASELINE_V1'

function fmtInt(n: number): string {
  return n.toLocaleString('fr-FR')
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

function fmtWhen(iso: string | null): string {
  if (!iso) return 'jamais'
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return '—'
  const ageSec = (Date.now() - t) / 1000
  if (ageSec < 3600) return `il y a ${Math.max(1, Math.floor(ageSec / 60))} min`
  if (ageSec < 86400) return `il y a ${Math.floor(ageSec / 3600)} h`
  return `il y a ${Math.floor(ageSec / 86400)} j`
}

const STAGE_LABELS: Record<string, string> = {
  direction: 'Direction',
  participation: 'Participation',
  structure: 'Structure',
  location: 'Emplacement',
  regime: 'Régime',
}

type LoadProps = { loading?: boolean; empty?: boolean; error?: string | null }

export function MarketPulseCard({
  rows,
  loading,
}: {
  rows: ScreenerDecisionRow[]
} & LoadProps) {
  const stats = summarizeScreener(rows)
  return (
    <section className="panel" aria-label="Market pulse">
      <header className="panel-head">
        <h2>Market pulse</h2>
        <span className="muted">Distribution actuelle</span>
      </header>
      {loading && !rows.length ? (
        <p className="muted card-body">Chargement…</p>
      ) : !rows.length ? (
        <p className="muted card-body">Aucun marché scanné.</p>
      ) : (
        <div className="card-body iv-pulse" style={{ padding: '0.75rem 1rem 1.1rem' }}>
          <div
            className="iv-donut"
            style={
              {
                ['--buy' as string]: stats.total ? ((stats.buy / stats.total) * 100).toFixed(2) : 0,
                ['--sell' as string]: stats.total ? ((stats.sell / stats.total) * 100).toFixed(2) : 0,
                ['--watch' as string]: stats.total
                  ? ((stats.watch / stats.total) * 100).toFixed(2)
                  : 0,
              } as CSSProperties
            }
            data-center={String(stats.total)}
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
      )}
    </section>
  )
}

export function PipelineHealthCard({
  rows,
  loading,
}: {
  rows: ScreenerDecisionRow[]
} & LoadProps) {
  const { stagePass, total } = summarizeScreener(rows)
  return (
    <section className="panel" aria-label="Pipeline health">
      <header className="panel-head">
        <h2>Pipeline health</h2>
        <span className="muted">Portes passées · screener 1h</span>
      </header>
      {loading && !rows.length ? (
        <p className="muted card-body">Chargement…</p>
      ) : !rows.length ? (
        <p className="muted card-body">Pas encore de données pipeline.</p>
      ) : (
        <ul className="ov-pipeline-list card-body">
          {Object.entries(STAGE_LABELS).map(([id, label]) => {
            const n = stagePass[id] ?? 0
            const pct = total ? Math.round((n / total) * 100) : 0
            return (
              <li key={id}>
                <span>{label}</span>
                <div className="ov-pipeline-bar" aria-hidden>
                  <i style={{ width: `${pct}%` }} />
                </div>
                <b className="mono">
                  {n}/{total}
                </b>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

export function Circuit24Strip({
  summary,
  loading,
}: {
  summary: ActivitySummary | null
} & LoadProps) {
  const alive = (summary?.decisions.last_24h ?? 0) > 0
  return (
    <section className={`ov-circuit panel ov-pulse${alive ? ' is-ok' : ' is-warn'}`} aria-label="Circuit 24 h">
      <header className="panel-head">
        <h2>Circuit 24 h</h2>
        <span className="muted">{alive ? 'Actif' : 'Calme'}</span>
      </header>
      {loading && !summary ? (
        <p className="muted card-body">Chargement…</p>
      ) : !summary ? (
        <p className="muted card-body">Résumé activité indisponible.</p>
      ) : (
        <div className="ov-circuit-grid card-body">
          <div>
            <span className="muted">Décisions</span>
            <strong className="mono">{fmtInt(summary.decisions.last_24h)}</strong>
            <small className="muted">total {fmtInt(summary.decisions.total)}</small>
          </div>
          <div>
            <span className="muted">Paper ouverts</span>
            <strong className="mono">{fmtInt(summary.paper.open_now)}</strong>
            <small className="muted">{fmtInt(summary.paper.opened_total)} cumul</small>
          </div>
          <div>
            <span className="muted">Lab / backtests</span>
            <strong className="mono">{fmtInt(summary.backtest.runs_total)}</strong>
            <small className="muted">dernier {fmtWhen(summary.backtest.last_at)}</small>
          </div>
        </div>
      )}
    </section>
  )
}

export function EvidenceOpsCard({
  evidence,
  summary,
  loading,
}: {
  evidence: BacktestEvidenceSummary | null
  summary: ActivitySummary | null
} & LoadProps) {
  const edge = evidence?.pipeline_beats_ichimoku_sharpe
  return (
    <section className="panel ov-proof-block" aria-label="Preuves et opérations">
      <header className="panel-head">
        <h2>Preuves &amp; opérations</h2>
        <Link to="/app/operations" className="ghost">
          Opérations →
        </Link>
      </header>
      <div className="ov-proof-body card-body">
        {loading && !evidence && !summary ? (
          <p className="muted">Chargement…</p>
        ) : (
          <>
            <p className="ov-proof-lead">
              {edge == null ? (
                <>Edge pipeline vs Ichimoku : <span className="muted">pas encore de comparaison</span></>
              ) : edge ? (
                <>
                  Pipeline <span className="up">bat</span> Ichimoku (Sharpe) sur la dernière collecte.
                </>
              ) : (
                <>
                  Pipeline <span className="down">ne bat pas</span> encore Ichimoku (Sharpe).
                </>
              )}
            </p>
            <p className="ov-proof-note muted">
              {summary
                ? `${fmtInt(summary.shadow.blocked_total)} refusés · ${fmtInt(summary.evidence.measured)} signaux mesurés`
                : 'Ouvre Opérations pour le détail circuit / filtres / backtests.'}
            </p>
            <Link to="/app/strategy-lab" className="link">
              Strategy Lab ↗
            </Link>
          </>
        )}
      </div>
    </section>
  )
}

export function LabsPaperCard({
  portfolios,
  loading,
}: {
  portfolios: PaperPortfolioRow[]
} & LoadProps) {
  const labs = [...portfolios].sort((a, b) => {
    if (a.code === BASELINE) return -1
    if (b.code === BASELINE) return 1
    return b.realized_pnl - a.realized_pnl
  })
  return (
    <section className="panel ov-labs" aria-label="Labs paper">
      <header className="panel-head">
        <h2>Labs paper</h2>
        <Link to="/app/portefeuille" className="ghost">
          Portefeuille →
        </Link>
      </header>
      {loading && !labs.length ? (
        <p className="muted card-body">Chargement…</p>
      ) : !labs.length ? (
        <p className="muted card-body">Aucun portefeuille paper actif.</p>
      ) : (
        <div className="table-wrap card-body">
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
  )
}
