/**
 * Structure de marché : swings (HH / HL / LH / LL, type=text) et événements
 * BOS / CHOCH (type=marker, layer=breaks). Chaque marqueur = un objet Python.
 */

import type { IntelligenceObject } from '../../lib/chartIntelligence'
import { Chip } from './DrawingLayer'
import { useDrawingLayer } from './drawingContext'

export function MarketStructureLayer() {
  const { proj, objects, isSelected, select } = useDrawingLayer('market_structure')
  if (!proj) return null
  const swings = objects.filter((o) => o.origin.kind === 'swing')
  const events = objects.filter((o) => o.origin.kind !== 'swing')
  return (
    <g className="ci-layer ci-layer-structure">
      {events.map((o) => (
        <StructureEvent key={o.id} o={o} selected={isSelected(o)} onSelect={() => select(o)} />
      ))}
      {swings.map((o) => (
        <SwingLabel key={o.id} o={o} selected={isSelected(o)} onSelect={() => select(o)} />
      ))}
    </g>
  )
}

interface ItemProps {
  o: IntelligenceObject
  selected: boolean
  onSelect: () => void
}

function SwingLabel({ o, selected, onSelect }: ItemProps) {
  const { proj } = useDrawingLayer('market_structure')
  const p = o.points[0]
  if (!proj || !p) return null
  const x = proj.x(p.time)
  const y = proj.y(p.price)
  if (x == null || y == null) return null
  const high = o.origin.swing === 'HH' || o.origin.swing === 'LH'
  const tone = o.origin.swing === 'HH' || o.origin.swing === 'HL' ? 'bull' : 'bear'
  return (
    <g className={`ci-swing ci-tone-${tone}${selected ? ' is-selected' : ''}`}>
      <circle className="ci-swing-dot" cx={x} cy={y} r={2.5} />
      <text
        className="ci-hit ci-swing-text"
        x={x}
        y={high ? y - 8 : y + 16}
        textAnchor="middle"
        onClick={onSelect}
      >
        {o.label}
      </text>
    </g>
  )
}

function StructureEvent({ o, selected, onSelect }: ItemProps) {
  const { proj } = useDrawingLayer('market_structure')
  const p = o.points[0]
  if (!proj || !p) return null
  const xb = proj.x(p.time)
  const y = proj.y(o.origin.level ?? p.price)
  const xs = o.origin.swing_time != null ? proj.x(o.origin.swing_time) : null
  if (xb == null || y == null) return null
  const x0 = xs ?? xb - proj.barSpacing * 6
  const bullish = o.origin.direction !== 'bearish'
  const tone = bullish ? 'bull' : 'bear'
  const text = `${o.origin.event_type === 'CHOCH' ? 'CHOCH' : 'BOS'}${o.origin.internal ? ' (int.)' : ''}`
  return (
    <g className={`ci-event ci-tone-${tone}${o.origin.internal ? ' is-internal' : ''}${selected ? ' is-selected' : ''}`}>
      <line className="ci-hit ci-hit-stroke" x1={x0} x2={xb} y1={y} y2={y} onClick={onSelect} />
      <line className="ci-event-line" x1={x0} x2={xb} y1={y} y2={y} />
      <Chip
        x={(x0 + xb) / 2}
        y={bullish ? y - 10 : y + 10}
        text={text}
        tone={tone}
        align="middle"
        proj={proj}
        strong={selected}
        onClick={onSelect}
      />
    </g>
  )
}
