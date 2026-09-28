import { Fragment } from 'react'
import { labelDecision, labelPipelineGate } from '../lib/decisionLabels'
import type { DecisionLabel, DecisionPipelinePayload } from '../lib/decisions'
import { isActionableBuySell } from '../lib/vpValidationCopy'
import { asGate, decisionTone, gateTone } from '../lib/verdict'
import { VpValidationBadge } from './VpValidationBadge'

interface Props {
  decision: DecisionLabel | string
  pipeline?: DecisionPipelinePayload
  hideDiagnostic?: boolean
  variant?: 'cell' | 'detail'
}

export function VerdictBadge({ decision, pipeline, hideDiagnostic, variant = 'cell' }: Props) {
  const gate = asGate(pipeline?.decision as string | undefined)
  const showVp = isActionableBuySell(gate) || (!gate && isActionableBuySell(decision))

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
        {showVp ? <VpValidationBadge compact={variant === 'cell'} /> : null}
        {!hideDiagnostic && (
          <span
            className={diagClass}
            title={`Signal brut avant Structure/Location/Régime · ${decision}`}
          >
            {diagText}
          </span>
        )}
      </Wrap>
    )
  }

  return (
    <span className="decision-cell-stack">
      <span
        className={`bias bias-${decisionTone(decision)}`}
        title={`Combiner (pas de pipeline) · ${decision}`}
      >
        {labelDecision(decision as DecisionLabel)}
      </span>
      {showVp ? <VpValidationBadge compact={variant === 'cell'} /> : null}
    </span>
  )
}
