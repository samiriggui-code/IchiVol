import { useMemo } from 'react'
import { summarizeScreener } from '../../lib/deskSummarize'
import {
  PIPELINE_STAGE_ORDER,
  stageFullLabel,
  stageMatrixLabel,
} from '../../lib/decisionPipeline'
import type { ScreenerDecisionRow } from '../../lib/decisions'

export function PipelineRibbon({
  rows,
  loading,
}: {
  rows: ScreenerDecisionRow[]
  loading: boolean
}) {
  const summary = useMemo(() => summarizeScreener(rows), [rows])
  const stages = PIPELINE_STAGE_ORDER.map((id) => ({
    id,
    label: stageFullLabel(id),
    short: stageMatrixLabel(id),
    pass: summary.stagePass[id] ?? 0,
  }))
  return (
    <section className="panel opp-pipeline-ribbon" aria-label="De l'observation à la décision">
      <header className="panel-head">
        <h2>De l’observation à la décision</h2>
        <span className="panel-meta">
          {loading && !rows.length ? '…' : `${summary.total} symboles · portes passées`}
        </span>
      </header>
      <ol className="opp-ribbon">
        {stages.map((s, i) => (
          <li key={s.id}>
            {i > 0 ? <span className="opp-ribbon-arrow" aria-hidden>→</span> : null}
            <div className="opp-ribbon-step">
              <span className="muted">{s.short}</span>
              <strong>{s.label}</strong>
              <b className="mono">{loading && !rows.length ? '—' : s.pass}</b>
            </div>
          </li>
        ))}
        <li>
          <span className="opp-ribbon-arrow" aria-hidden>→</span>
          <div className="opp-ribbon-step is-gate">
            <span className="muted">Portes</span>
            <strong>Décision</strong>
            <b className="mono">
              {loading && !rows.length
                ? '—'
                : `${summary.buy + summary.sell} act.`}
            </b>
            <small className="muted">
              {summary.buy} A · {summary.sell} V · {summary.watch} W · {summary.none} NT
            </small>
          </div>
        </li>
      </ol>
    </section>
  )
}
