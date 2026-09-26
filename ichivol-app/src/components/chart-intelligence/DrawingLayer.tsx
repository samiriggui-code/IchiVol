/**
 * DrawingLayer — surface SVG superposée au graphique. Fournit aux couches
 * enfants (MarketStructureLayer, FibonacciLayer…) les objets visibles, la
 * sélection et la projection temps/prix → pixels.
 */

import type { ReactNode } from 'react'
import type { IntelligenceObject } from '../../lib/chartIntelligence'
import { useChartProjection, type ChartProjection } from './chartProjection'
import {
  COMPACT_WIDTH,
  DrawingContext,
  gutterEntries,
  layoutGutter,
  textWidth,
  type DrawTone,
} from './drawingContext'

interface Props {
  objects: IntelligenceObject[]
  selectedKey: string | null
  onSelect: (key: string) => void
  /** Instant as_of courant (bord droit des objets vivants). */
  asOf: number | null
  /** Clés apparues sur la dernière bougie du curseur. */
  freshKeys?: ReadonlySet<string>
  /** Atténue les objets non « fresh » pendant le replay. */
  dimStale?: boolean
  children: ReactNode
}

export function DrawingLayer({
  objects,
  selectedKey,
  onSelect,
  asOf,
  freshKeys,
  dimStale = false,
  children,
}: Props) {
  const proj = useChartProjection()
  if (!proj) return null
  const fresh = freshKeys ?? new Set<string>()
  return (
    <DrawingContext.Provider value={{ objects, selectedKey, onSelect, asOf, freshKeys: fresh, dimStale }}>
      <svg
        className={`ci-drawing-svg${dimStale ? ' is-replay' : ''}`}
        width={proj.width}
        height={proj.height}
        viewBox={`0 0 ${proj.width} ${proj.height}`}
        role="group"
        aria-label="Objets graphiques Chart Intelligence"
      >
        <defs>
          <pattern id="ci-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="6" className="ci-hatch-line" />
          </pattern>
          <clipPath id="ci-plot-clip">
            <rect x="0" y="0" width={proj.width} height={proj.height} />
          </clipPath>
        </defs>
        <g clipPath="url(#ci-plot-clip)">
          {children}
          <GutterLabels
            objects={objects}
            proj={proj}
            asOf={asOf}
            selectedKey={selectedKey}
            onSelect={onSelect}
            freshKeys={fresh}
            dimStale={dimStale}
          />
        </g>
      </svg>
    </DrawingContext.Provider>
  )
}

/* ------------------------------------------------------------------ */
/* Primitive SVG partagée                                              */
/* ------------------------------------------------------------------ */

interface ChipProps {
  x: number
  y: number
  text: string
  tone: DrawTone
  /** 'start' : chip à droite de x ; 'end' : à gauche ; 'middle' : centré. */
  align?: 'start' | 'end' | 'middle'
  proj: ChartProjection
  strong?: boolean
  onClick?: () => void
}

/** Étiquette compacte (DM Mono), maintenue dans la zone de tracé. */
export function Chip({ x, y, text, tone, align = 'start', proj, strong, onClick }: ChipProps) {
  const w = textWidth(text) + 10
  const h = 16
  let left = align === 'start' ? x : align === 'end' ? x - w : x - w / 2
  left = Math.max(2, Math.min(proj.width - w - 2, left))
  const top = Math.max(2, Math.min(proj.height - h - 2, y - h / 2))
  return (
    <g
      className={`ci-chip ci-tone-${tone}${strong ? ' is-strong' : ''}${onClick ? ' ci-hit' : ''}`}
      onClick={onClick}
    >
      <rect x={left} y={top} width={w} height={h} rx={3} />
      <text x={left + 5} y={top + h / 2 + 3.5}>
        {text}
      </text>
    </g>
  )
}

interface GutterProps {
  objects: IntelligenceObject[]
  proj: ChartProjection
  asOf: number | null
  selectedKey: string | null
  onSelect: (key: string) => void
  freshKeys: ReadonlySet<string>
  dimStale: boolean
}

/** Max d’étiquettes gouttière — évite la pollution visuelle. */
const MAX_GUTTER = 8

/** Étiquettes des objets vivants, empilées à droite du dernier prix (sans chevauchement). */
function GutterLabels({ objects, proj, asOf, selectedKey, onSelect, freshKeys, dimStale }: GutterProps) {
  const compact = proj.width < COMPACT_WIDTH
  const entries = gutterEntries(objects, proj, asOf)
  // Priorité : sélection > fresh > le reste (cap pour lisibilité).
  const ranked = [...entries].sort((a, b) => {
    const sa = selectedKey === a.selKey ? 2 : freshKeys.has(a.selKey) ? 1 : 0
    const sb = selectedKey === b.selKey ? 2 : freshKeys.has(b.selKey) ? 1 : 0
    return sb - sa
  })
  const kept = ranked.slice(0, MAX_GUTTER)
  const placed = layoutGutter(kept, proj.height, compact ? 15 : 17)
  return (
    <g className="ci-gutter">
      {placed.map((e) => {
        const x = e.fromX + 14
        const moved = Math.abs(e.ly - e.y) > 1
        const fresh = freshKeys.has(e.selKey)
        const dim = dimStale && !fresh && selectedKey !== e.selKey
        return (
          <g
            key={e.id}
            className={`ci-tone-${e.tone}${fresh ? ' is-fresh' : ''}${dim ? ' is-dim' : ''}`}
          >
            <path
              className={`ci-leader${moved ? ' is-moved' : ''}`}
              d={`M${e.fromX},${e.y} L${e.fromX + 7},${e.y} L${x - 1},${e.ly}`}
            />
            <Chip
              x={x}
              y={e.ly}
              text={compact && selectedKey !== e.selKey ? e.short : e.text}
              tone={e.tone}
              proj={proj}
              strong={selectedKey === e.selKey || fresh}
              onClick={() => onSelect(e.selKey)}
            />
          </g>
        )
      })}
    </g>
  )
}
