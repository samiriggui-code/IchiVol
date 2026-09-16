import { labelDecision, labelPipelineGate } from '../lib/decisionLabels'
import type { DecisionLabel, DecisionPipelinePayload } from '../lib/decisions'
import { asGate, decisionTone, gateTone } from '../lib/verdict'

interface Props {
  decision: DecisionLabel | string
  pipeline?: DecisionPipelinePayload
  /** Masque la ligne diagnostic (combiner) quand une porte est dispo — utile en contexte très dense. */
  hideDiagnostic?: boolean
}

/**
 * Rendu Option B unique (docs/OPTIONS-ABC.md) : porte = badge d'action ;
 * combiner legacy = diagnostic secondaire "brut". Sans porte dispo, on
 * retombe sur le combiner seul, étiqueté comme tel dans le title.
 */
export function VerdictBadge({ decision, pipeline, hideDiagnostic }: Props) {
  const gate = asGate(pipeline?.decision as string | undefined)

  if (gate) {
    return (
      <span className="decision-cell-stack">
        <span className={`bias bias-${gateTone(gate)}`} title={`Portes · ${gate}`}>
          {labelPipelineGate(gate)}
        </span>
        {!hideDiagnostic && (
          <span
            className="decision-cell-diag muted"
            title={`Brut Ichi+RVOL (combiner legacy) · ${decision}`}
          >
            brut {labelDecision(decision as DecisionLabel)}
          </span>
        )}
      </span>
    )
  }

  return (
    <span
      className={`bias bias-${decisionTone(decision)}`}
      title={`Combiner (pas de pipeline) · ${decision}`}
    >
      {labelDecision(decision as DecisionLabel)}
    </span>
  )
}
