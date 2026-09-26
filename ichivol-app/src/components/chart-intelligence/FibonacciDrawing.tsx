/**
 * Fibonacci — un dessin = N ChartObjects `horizontal_line` layer=fibonacci
 * partageant origin.group_id (format engine T9e). Les prix des niveaux et les
 * ancres viennent de Python ; React ne fait que les tracer.
 */

import {
  fmtPct,
  fmtPrice,
  producerLabel,
  selectionKeyOf,
  type IntelligenceObject,
} from '../../lib/chartIntelligence'
import { Chip } from './DrawingLayer'
import { COMPACT_WIDTH, rightEdge, useDrawingLayer } from './drawingContext'

export function FibonacciLayer() {
  const { proj, objects, asOf, isSelected, select } = useDrawingLayer('fibonacci')
  if (!proj) return null
  const groups = new Map<string, IntelligenceObject[]>()
  for (const o of objects) {
    const k = selectionKeyOf(o)
    groups.set(k, [...(groups.get(k) ?? []), o])
  }
  return (
    <g className="ci-layer ci-layer-fib">
      {[...groups.entries()].map(([k, levels]) => (
        <FibonacciDrawing
          key={k}
          levels={levels}
          asOf={asOf}
          selected={isSelected(levels[0]!)}
          onSelect={() => select(levels[0]!)}
        />
      ))}
    </g>
  )
}

interface Props {
  levels: IntelligenceObject[]
  asOf: number | null
  selected: boolean
  onSelect: () => void
}

const KEY_RATIOS = new Set([0.5, 0.618, 0.786])

export function FibonacciDrawing({ levels, asOf, selected, onSelect }: Props) {
  const { proj } = useDrawingLayer('fibonacci')
  const head = levels[0]
  if (!proj || !head) return null
  const a0 = head.origin.anchor_start
  const a1 = head.origin.anchor_end
  const xs = a0 ? proj.x(a0.time) : null
  const xe = a1 ? proj.x(a1.time) : null
  const x0 = Math.max(0, xs ?? 0)
  const xr = rightEdge(proj, asOf)
  const sorted = [...levels].sort((a, b) => (a.origin.ratio ?? 0) - (b.origin.ratio ?? 0))
  const ya0 = a0 ? proj.y(a0.price) : null
  const ya1 = a1 ? proj.y(a1.price) : null
  const tf = head.timeframe.toUpperCase()

  return (
    <g className={`ci-fib${selected ? ' is-selected' : ''}`}>
      {sorted.map((lv) => {
        const price = lv.points[0]?.price
        const y = price != null ? proj.y(price) : null
        if (y == null || price == null) return null
        const ratio = lv.origin.ratio ?? Number(lv.label)
        const key = KEY_RATIOS.has(ratio)
        return (
          <g key={lv.id} className={`ci-fib-level${key ? ' is-key' : ''}`}>
            <line className="ci-hit ci-hit-stroke" x1={x0} x2={xr} y1={y} y2={y} onClick={onSelect} />
            <line className="ci-fib-line" x1={x0} x2={xr} y1={y} y2={y} />          </g>
        )
      })}
      {xs != null && xe != null && ya0 != null && ya1 != null && (
        <g className="ci-fib-anchors">
          <line className="ci-fib-diag" x1={xs} y1={ya0} x2={xe} y2={ya1} />
          <circle className="ci-anchor ci-hit" cx={xs} cy={ya0} r={4} onClick={onSelect} />
          <circle className="ci-anchor ci-hit" cx={xe} cy={ya1} r={4} onClick={onSelect} />
          <Chip x={xs} y={ya0 + 14} text={`SWING LOW ${fmtPrice(a0!.price)}`} tone="fib" align="middle" proj={proj} />
          <Chip x={xe} y={ya1 - 34} text={`SWING HIGH ${fmtPrice(a1!.price)}`} tone="fib" align="middle" proj={proj} />
        </g>
      )}
      {ya1 != null && (
        <Chip
          x={x0}
          y={ya1 - 16}
          text={
            proj.width < COMPACT_WIDTH && !selected
              ? `AUTO FIB · ${fmtPct(head.confidence)}`
              : `AUTO FIB · ${producerLabel(head)} · ${tf} · Confidence ${fmtPct(head.confidence)}`
          }
          tone="fib"
          proj={proj}
          strong={selected}
          onClick={onSelect}
        />
      )}
    </g>
  )
}
