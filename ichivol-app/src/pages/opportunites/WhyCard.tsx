import { DeskCardShell } from '../../components/desk/DeskRings'
import {
  buildDecisionSummary,
  labelDecision,
  labelPipelineGate,
} from '../../lib/decisionLabels'
import {
  stageFullLabel,
  type PipelineStageId,
} from '../../lib/decisionPipeline'
import type { DecisionDetail, ScreenerDecisionRow } from '../../lib/decisions'
import { rowGate } from './shared'

export function WhyCard({
  whyCandidate,
  whyDetail,
  whyLoading,
  whyError,
  onOpenSheet,
}: {
  whyCandidate: ScreenerDecisionRow
  whyDetail: DecisionDetail | null
  whyLoading: boolean
  whyError: string | null
  onOpenSheet: (symbol: string) => void
}) {
  const g = rowGate(whyCandidate)
  return (
    <DeskCardShell
      title={`Pourquoi ${whyCandidate.symbol.replace(/USDT$/i, '')} ?`}
      meta={g ? labelPipelineGate(g) : labelDecision(whyCandidate.decision)}
      footer={
        <button type="button" className="link" onClick={() => onOpenSheet(whyCandidate.symbol)}>
          Ouvrir la fiche ↗
        </button>
      }
    >
      {whyLoading && !whyDetail ? (
        <p className="muted">Chargement du détail…</p>
      ) : whyError && !whyDetail ? (
        <p className="muted">{whyError}</p>
      ) : whyDetail ? (
        <div className="opp-why">
          <p className="opp-why-summary">{buildDecisionSummary(whyDetail)}</p>
          <ul className="opp-why-stages">
            {(whyDetail.pipeline?.stages ?? []).map((s) => (
              <li key={s.id} className={`is-${s.status}`}>
                <span>{stageFullLabel(s.id as PipelineStageId)}</span>
                <strong>
                  {s.status === 'pass' ? 'passée' : s.status === 'fail' ? 'bloquée' : s.status}
                </strong>
                {s.summary ? <small className="muted">{s.summary}</small> : null}
              </li>
            ))}
          </ul>
          <dl className="opp-why-meta">
            <div>
              <dt>RVOL</dt>
              <dd className="mono">
                {whyDetail.rvol != null
                  ? `${new Intl.NumberFormat('fr-FR', {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    }).format(whyDetail.rvol)}×`
                  : '—'}
              </dd>
            </div>
            <div>
              <dt>Invalidation</dt>
              <dd>
                {(whyDetail.invalidation && whyDetail.invalidation[0]) ||
                  whyDetail.evidence?.invalidation?.[0] ||
                  whyDetail.order_intent?.invalidation?.[0] ||
                  '—'}
              </dd>
            </div>
          </dl>
        </div>
      ) : (
        <p className="muted">Pas encore de détail pour ce symbole.</p>
      )}
    </DeskCardShell>
  )
}
