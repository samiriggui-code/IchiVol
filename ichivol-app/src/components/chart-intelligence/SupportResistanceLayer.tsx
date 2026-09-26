/** Supports / résistances : zones (price_low → price_high) fournies par Python. */

import type { IntelligenceObject } from '../../lib/chartIntelligence'
import { rightEdge, useDrawingLayer } from './drawingContext'

export function SupportResistanceLayer() {
  const { proj, objects, asOf, isSelected, select } = useDrawingLayer('support_resistance')
  if (!proj) return null
  return (
    <g className="ci-layer ci-layer-sr">
      {objects.map((o) => (
        <SupportResistanceZone
          key={o.id}
          o={o}
          asOf={asOf}
          selected={isSelected(o)}
          onSelect={() => select(o)}
        />
      ))}
    </g>
  )
}

interface ZoneProps {
  o: IntelligenceObject
  asOf: number | null
  selected: boolean
  onSelect: () => void
}

export function SupportResistanceZone({ o, asOf, selected, onSelect }: ZoneProps) {
  const { proj } = useDrawingLayer('support_resistance')
  if (!proj || o.price_low == null || o.price_high == null) return null
  const yTop = proj.y(o.price_high)
  const yBot = proj.y(o.price_low)
  if (yTop == null || yBot == null) return null
  const start = o.points[0]?.time
  const x0 = Math.max(0, start != null ? (proj.x(start) ?? 0) : 0)
  const x1 = rightEdge(proj, o.points[1]?.time ?? asOf)
  if (x1 <= x0) return null
  const support = o.side !== 'resistance'
  const tone = support ? 'bull' : 'bear'
  return (
    <g className={`ci-sr ci-tone-${tone}${selected ? ' is-selected' : ''}${o.origin.htf ? ' is-htf' : ''}`}>
      <rect
        className="ci-hit ci-zone-fill"
        x={x0}
        y={Math.min(yTop, yBot)}
        width={x1 - x0}
        height={Math.max(2, Math.abs(yBot - yTop))}
        onClick={onSelect}
      />
      <line className="ci-zone-edge" x1={x0} x2={x1} y1={yTop} y2={yTop} />
      <line className="ci-zone-edge" x1={x0} x2={x1} y1={yBot} y2={yBot} />    </g>
  )
}
