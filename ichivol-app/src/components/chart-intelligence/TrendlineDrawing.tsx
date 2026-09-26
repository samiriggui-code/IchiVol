/** Trendlines / rays (2 points Python). Un ray est prolongé jusqu'au bord as_of. */

import type { IntelligenceObject } from '../../lib/chartIntelligence'
import { rightEdge, useDrawingLayer } from './drawingContext'

export function TrendlineLayer() {
  const { proj, objects, asOf, isSelected, select } = useDrawingLayer('trendlines')
  if (!proj) return null
  return (
    <g className="ci-layer ci-layer-trend">
      {objects.map((o) => (
        <TrendlineDrawing key={o.id} o={o} asOf={asOf} selected={isSelected(o)} onSelect={() => select(o)} />
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

export function TrendlineDrawing({ o, asOf, selected, onSelect }: Props) {
  const { proj } = useDrawingLayer('trendlines')
  if (!proj || o.points.length < 2) return null
  const [p0, p1] = o.points as [{ time: number; price: number }, { time: number; price: number }]
  const x0 = proj.x(p0.time)
  const y0 = proj.y(p0.price)
  const xa = proj.x(p1.time)
  const ya = proj.y(p1.price)
  if (x0 == null || y0 == null || xa == null || ya == null || xa === x0) return null
  // Prolongement géométrique en pixels du segment fourni (affichage, pas de calcul de marché).
  let x1 = xa
  let y1 = ya
  if (o.type === 'ray') {
    x1 = rightEdge(proj, asOf)
    y1 = y0 + ((ya - y0) * (x1 - x0)) / (xa - x0)
  }
  const tone = o.side === 'resistance' ? 'bear' : 'bull'
  const d = `M${x0},${y0} L${x1},${y1}`
  return (
    <g className={`ci-trend ci-tone-${tone}${selected ? ' is-selected' : ''}`}>
      <path className="ci-hit ci-hit-stroke" d={d} onClick={onSelect} />
      <path className="ci-trend-line" d={d} />
      {[p0, p1].map((p) => {
        const x = proj.x(p.time)
        const y = proj.y(p.price)
        return x == null || y == null ? null : <circle key={p.time} className="ci-anchor" cx={x} cy={y} r={3} />
      })}    </g>
  )
}
