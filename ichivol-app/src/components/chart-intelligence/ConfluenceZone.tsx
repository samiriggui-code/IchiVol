/**
 * Zone de confluence (layer=confluence). Score et composants = données Python.
 * Tant que origin.score_is_mock est vrai, le score est marqué « (mock) » (étiquette
 * dans la gouttière droite, cf. DrawingLayer).
 */

import type { IntelligenceObject } from '../../lib/chartIntelligence'
import { rightEdge, useDrawingLayer } from './drawingContext'

export function ConfluenceLayer() {
  const { proj, objects, asOf, isSelected, select } = useDrawingLayer('confluence')
  if (!proj) return null
  return (
    <g className="ci-layer ci-layer-conf">
      {objects.map((o) => (
        <ConfluenceZone key={o.id} o={o} asOf={asOf} selected={isSelected(o)} onSelect={() => select(o)} />
      ))}
    </g>
  )
}

interface Props {
  o: IntelligenceObject
  asOf: number | null
  selected: boolean
  onSelect: () => void
}

export function ConfluenceZone({ o, asOf, selected, onSelect }: Props) {
  const { proj } = useDrawingLayer('confluence')
  if (!proj || o.price_low == null || o.price_high == null) return null
  const yTop = proj.y(o.price_high)
  const yBot = proj.y(o.price_low)
  const xs = o.points[0] ? proj.x(o.points[0].time) : null
  if (yTop == null || yBot == null) return null
  const x0 = Math.max(0, xs ?? 0)
  const x1 = rightEdge(proj, o.points[1]?.time ?? asOf)
  return (
    <g className={`ci-conf${selected ? ' is-selected' : ''}`}>
      <rect
        className="ci-hit ci-conf-rect"
        x={x0}
        y={Math.min(yTop, yBot)}
        width={Math.max(2, x1 - x0)}
        height={Math.max(3, Math.abs(yBot - yTop))}
        onClick={onSelect}
      />
      <rect
        className="ci-conf-hatch"
        x={x0}
        y={Math.min(yTop, yBot)}
        width={Math.max(2, x1 - x0)}
        height={Math.max(3, Math.abs(yBot - yTop))}
      />    </g>
  )
}
