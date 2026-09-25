import { Fragment } from 'react'
import { labelDecision, labelPipelineGate } from '../lib/decisionLabels'
import type { DecisionLabel, DecisionPipelinePayload } from '../lib/decisions'
import { asGate, decisionTone, gateTone } from '../lib/verdict'

interface Props {
  decision: DecisionLabel | string
  pipeline?: DecisionPipelinePayload
  /** Masque la ligne diagnostic (combiner) quand une porte est dispo — utile en contexte très dense. */
  hideDiagnostic?: boolean
  /** 'cell' = table dense (défaut) ; 'detail' = hero du sheet décision (boîte pointillée, libellé long). */
  variant?: 'cell' | 'detail'
}

/**
 * Rendu Option B unique (docs/OPTIONS-ABC.md) : porte = badge d'action ;
 * combiner legacy = diagnostic secondaire "brut". Sans porte dispo, on
 * retombe sur le combiner seul, étiqueté comme tel dans le title.
 */
export function VerdictBadge({ decision, pipeline, hideDiagnostic, variant = 'cell' }: Props) {
  const gate = asGate(pipeline?.decision as string | undefined)

  if (gate) {
    const diagClass = variant === 'detail' ? 'decision-detail-diag muted' : 'decision-cell-diag muted'
    const diagText =
      variant === 'detail'
        ? `Brut Ichi+RVOL · ${labelDecision(decision as DecisionLabel)}`
        : `brut ${labelDecision(decision as DecisionLabel)}`
    const Wrap = variant === 'detail' ? Fragment : 'span'
    const wrapProps = variant === 'detail' ? {} : { className: 'decision-cell-stack' }
    return (
      <Wrap {...wrapProps}>
        <span className={`bias bias-${gateTone(gate)}`} title={`Portes · ${gate}`}>
          {labelPipelineGate(gate)}
        </span>
        {!hideDiagnostic && (
          <span
            className={diagClass}
            title={`Signal brut avant Structure/Location/Régime (combiner legacy) · ${decision}`}
          >
            {diagText}
          </span>
        )}
      </Wrap>
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
