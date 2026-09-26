/** Liquidité (BSL / SSL) — segments horizontaux layer=liquidity (ajout de layer proposé). */

import { fmtPrice, STATUS_LABELS, type IntelligenceObject } from '../../lib/chartIntelligence'
import { Chip } from './DrawingLayer'
import { useDrawingLayer } from './drawingContext'

export function LiquidityLayer() {
  const { proj, objects, isSelected, select } = useDrawingLayer('liquidity')
  if (!proj) return null
  return (
    <g className="ci-layer ci-layer-liq">
      {objects.map((o) => (
        <LiquidityDrawing key={o.id} o={o} selected={isSelected(o)} onSelect={() => select(o)} />
      ))}
    </g>
  )
}

interface Props {
  o: IntelligenceObject
  selected: boolean
  onSelect: () => void
}

export function LiquidityDrawing({ o, selected, onSelect }: Props) {
  const { proj } = useDrawingLayer('liquidity')
  const [p0, p1] = o.points
  if (!proj || !p0 || !p1) return null
  const x0 = proj.x(p0.time)
  const x1 = proj.x(p1.time)
  const y = proj.y(p0.price)
  if (x0 == null || x1 == null || y == null) return null
  const status = o.origin.status ?? 'open'
  const text = `${o.label ?? 'LIQ'} ${fmtPrice(p0.price)} · ${STATUS_LABELS[status]}`
  return (
    <g className={`ci-liq is-${status}${selected ? ' is-selected' : ''}`}>
      <line className="ci-hit ci-hit-stroke" x1={x0} x2={x1} y1={y} y2={y} onClick={onSelect} />
      <line className="ci-liq-line" x1={x0} x2={x1} y1={y} y2={y} />
      {status === 'swept' && <circle className="ci-liq-sweep" cx={x1} cy={y} r={4} />}
      <Chip
        x={x0 + 4}
        y={o.side === 'resistance' ? y - 10 : y + 10}
        text={text}
        tone="liq"
        proj={proj}
        strong={selected}
        onClick={onSelect}
      />
    </g>
  )
}
