/**
 * BriefingControls — période (fenêtre) + packs calques.
 * Caméra dérivée de la période (follow N barres / fit). Directeur V0 = heuristique
 * contextuelle ; Eve pourra proposer plus tard (humain confirme).
 */

import {
  BRIEFING_PERIODS,
  LAYER_PACKS,
  type BriefingPeriodId,
  type LayerPackId,
} from '../../lib/chartIntelligenceBriefing'

interface Props {
  period: BriefingPeriodId
  pack: LayerPackId | null
  onPeriod: (id: BriefingPeriodId) => void
  onPack: (id: LayerPackId) => void
}

export function BriefingControls({ period, pack, onPeriod, onPack }: Props) {
  return (
    <div className="ci-briefing" role="group" aria-label="Briefing graphique">
      <div className="ci-briefing-row">
        <span className="ci-briefing-label">Période</span>
        <div className="ci-briefing-seg" role="group" aria-label="Période visible">
          {BRIEFING_PERIODS.map((p) => (
            <button
              key={p.id}
              type="button"
              className={period === p.id ? 'is-on' : undefined}
              title={p.hint}
              onClick={() => onPeriod(p.id)}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>
      <div className="ci-briefing-row">
        <span className="ci-briefing-label">Pack</span>
        <div className="ci-briefing-seg" role="group" aria-label="Pack de calques">
          {LAYER_PACKS.map((p) => (
            <button
              key={p.id}
              type="button"
              className={pack === p.id ? 'is-on' : undefined}
              title={p.hint}
              onClick={() => onPack(p.id)}
            >
              {p.label}
            </button>
          ))}
          {pack == null && (
            <span className="ci-briefing-custom mono" title="Calques modifiés à la main">
              Perso
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
