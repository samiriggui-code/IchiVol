/**
 * BriefingControls — période (fenêtre) + packs calques.
 * Infobulles packs = couche UI additive (ne touche pas aux calques SVG / DrawingLayer).
 */

import { useId, useState } from 'react'
import {
  BRIEFING_PERIODS,
  LAYER_PACKS,
  type BriefingPeriodId,
  type LayerPack,
  type LayerPackId,
} from '../../lib/chartIntelligenceBriefing'
import { INTELLIGENCE_LAYER_META } from '../../lib/chartIntelligence'

interface Props {
  period: BriefingPeriodId
  pack: LayerPackId | null
  onPeriod: (id: BriefingPeriodId) => void
  onPack: (id: LayerPackId) => void
}

function PackTooltip({ pack }: { pack: LayerPack }) {
  const on = INTELLIGENCE_LAYER_META.filter((m) => pack.layers[m.key])
  return (
    <div className="ci-pack-tip" role="tooltip">
      <div className="ci-pack-tip-title">{pack.label}</div>
      <p className="ci-pack-tip-hint">{pack.hint}</p>
      <ul className="ci-pack-tip-layers">
        {on.map((m) => (
          <li key={m.key}>
            <span className="ci-pack-tip-dot" style={{ background: m.color }} aria-hidden />
            {m.label}
          </li>
        ))}
      </ul>
      <p className="ci-pack-tip-note">Preset d’affichage — aucun objet inventé.</p>
    </div>
  )
}

export function BriefingControls({ period, pack, onPeriod, onPack }: Props) {
  const tipBase = useId()
  const [openTip, setOpenTip] = useState<LayerPackId | null>(null)

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
          {LAYER_PACKS.map((p) => {
            const tipId = `${tipBase}-${p.id}`
            const show = openTip === p.id
            return (
              <span
                key={p.id}
                className="ci-pack-wrap"
                onMouseEnter={() => setOpenTip(p.id)}
                onMouseLeave={() => setOpenTip((cur) => (cur === p.id ? null : cur))}
                onFocus={() => setOpenTip(p.id)}
                onBlur={() => setOpenTip((cur) => (cur === p.id ? null : cur))}
              >
                <button
                  type="button"
                  className={pack === p.id ? 'is-on' : undefined}
                  aria-describedby={show ? tipId : undefined}
                  onClick={() => onPack(p.id)}
                >
                  {p.label}
                </button>
                {show ? (
                  <div id={tipId}>
                    <PackTooltip pack={p} />
                  </div>
                ) : null}
              </span>
            )
          })}
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
