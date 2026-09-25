import { useMemo } from 'react'
import {
  PIPELINE_STAGE_ORDER,
  stageFullLabel,
  stageMatrixLabel,
  stageStatusesFromRow,
  type PipelineStageId,
  type PipelineStageStatus,
} from '../../lib/decisionPipeline'
import type { ScreenerDecisionRow } from '../../lib/decisions'

export function MethodBanner({ rows }: { rows: ScreenerDecisionRow[] }) {
  const counts = useMemo(() => {
    const byStage: Record<PipelineStageId, Record<PipelineStageStatus, number>> = {
      direction: { pass: 0, fail: 0, watch: 0, pending: 0, skip: 0 },
      participation: { pass: 0, fail: 0, watch: 0, pending: 0, skip: 0 },
      structure: { pass: 0, fail: 0, watch: 0, pending: 0, skip: 0 },
      location: { pass: 0, fail: 0, watch: 0, pending: 0, skip: 0 },
      regime: { pass: 0, fail: 0, watch: 0, pending: 0, skip: 0 },
    }
    for (const row of rows) {
      const st = stageStatusesFromRow(row)
      for (const id of PIPELINE_STAGE_ORDER) {
        byStage[id][st[id]] += 1
      }
    }
    return byStage
  }, [rows])

  return (
    <section className="panel dec-method" aria-label="Méthode">
      <p className="dec-method-lead">
        Cinq portes successives. Seules <strong>Achat</strong> / <strong>Vente</strong> (colonne
        Portes) autorisent un ordre paper. <strong>Brut</strong> = Ichimoku + RVOL seul — diagnostic,
        pas un verdict d’action.
      </p>
      <ol className="dec-method-steps">
        {PIPELINE_STAGE_ORDER.map((id) => {
          const c = counts[id]
          const ok = c.pass
          const blocked = c.fail
          const soft = c.watch + c.pending
          return (
            <li key={id} title={stageFullLabel(id)}>
              <span className="dec-method-n">{stageMatrixLabel(id)}</span>
              <strong>{stageFullLabel(id)}</strong>
              <span className="muted dec-method-counts">
                <span className="up">{ok} ok</span>
                {' · '}
                <span className="down">{blocked} bloqué</span>
                {soft > 0 ? ` · ${soft} prudence` : ''}
              </span>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
