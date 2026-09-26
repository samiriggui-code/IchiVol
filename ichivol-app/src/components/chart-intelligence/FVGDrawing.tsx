/** Fair Value Gaps — rectangles layer=fvg (T9d). Statut et remplissage fournis par Python. */

import {
  fmtPrice,
  STATUS_LABELS,
  type IntelligenceObject,
} from '../../lib/chartIntelligence'
import { Chip } from './DrawingLayer'
import { rightEdge, useDrawingLayer } from './drawingContext'

export function FVGLayer() {
  const { proj, objects, asOf, isSelected, select } = useDrawingLayer('fvg')
  if (!proj) return null
  return (
    <g className="ci-layer ci-layer-fvg">
      {objects.map((o) => (
        <FVGDrawing key={o.id} o={o} asOf={asOf} selected={isSelected(o)} onSelect={() => select(o)} />
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

export function FVGDrawing({ o, asOf, selected, onSelect }: Props) {
  const { proj } = useDrawingLayer('fvg')
  if (!proj || o.price_low == null || o.price_high == null || !o.points[0]) return null
  const x0 = proj.x(o.points[0].time)
  const yTop = proj.y(o.price_high)
  const yBot = proj.y(o.price_low)
  if (x0 == null || yTop == null || yBot == null) return null
  const status = o.origin.status ?? 'open'
  // Une FVG comblée s'arrête à sa dernière date fournie ; sinon elle suit as_of.
  const end = o.points[1]?.time ?? asOf
  const x1 = status === 'filled' || status === 'invalidated' ? (proj.x(end ?? 0) ?? x0) : rightEdge(proj, end)
  const bearish = o.origin.direction === 'bearish'
  const tone = bearish ? 'bear' : 'bull'
  const label = `${bearish ? 'Bearish' : 'Bullish'} FVG ${fmtPrice(o.price_low)} → ${fmtPrice(o.price_high)} · ${STATUS_LABELS[status]}`
  return (
    <g className={`ci-fvg ci-tone-${tone} is-${status}${selected ? ' is-selected' : ''}`}>
      <rect
        className="ci-hit ci-fvg-rect"
        x={Math.max(0, x0)}
        y={Math.min(yTop, yBot)}
        width={Math.max(2, x1 - Math.max(0, x0))}
        height={Math.max(2, Math.abs(yBot - yTop))}
        onClick={onSelect}
      />
      {/* Étiquette sur place seulement pour une FVG terminée ; les vivantes sont dans la gouttière. */}
      {(status === 'filled' || status === 'invalidated') && (
      <Chip
        x={Math.max(0, x0) + 4}
        y={bearish ? Math.min(yTop, yBot) - 10 : Math.max(yTop, yBot) + 10}
        text={label}
        tone={tone}
        proj={proj}
        strong={selected}
        onClick={onSelect}
      />
      )}
    </g>
  )
}
