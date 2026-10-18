import { DECIDER_EXPLAIN, DECIDER_LABEL, type Decider } from '../../lib/decider'
import './DeciderBadge.css'

const TONE: Record<Decider, string> = {
  eve: ' is-eve',
  engine_over_eve: ' is-vs',
  manual: ' is-manual',
  engine: '',
}

/** Pastille « qui a décidé » : Ève, Moteur seul ou Manuel (l'explication est dans l'info-bulle et pour les lecteurs d'écran). */
export function DeciderBadge({ decider, compact = false }: { decider: Decider; compact?: boolean }) {
  return (
    <span
      className={`iv-decider${TONE[decider]} decider-badge is-${decider}${compact ? ' is-compact' : ''}`}
      title={DECIDER_EXPLAIN[decider]}
      aria-label={`${DECIDER_LABEL[decider]} : ${DECIDER_EXPLAIN[decider]}`}
    >
      <i aria-hidden="true" />
      {DECIDER_LABEL[decider]}
    </span>
  )
}
