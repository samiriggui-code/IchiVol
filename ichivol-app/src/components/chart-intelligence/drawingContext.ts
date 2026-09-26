/** Contexte + helpers partagés par DrawingLayer et les couches de dessin. */

import { createContext, useContext } from 'react'
import {
  fmtPct,
  fmtPrice,
  intelligenceLayerOf,
  selectionKeyOf,
  STATUS_LABELS,
  type IntelligenceLayerKey,
  type IntelligenceObject,
} from '../../lib/chartIntelligence'
import { useChartProjection, type ChartProjection } from './chartProjection'

export interface DrawingContextValue {
  objects: IntelligenceObject[]
  selectedKey: string | null
  onSelect: (key: string) => void
  asOf: number | null
  /** Clés apparues sur la dernière bougie (révélation PLAY). */
  freshKeys: ReadonlySet<string>
  /** true pendant un replay non-live → on atténue le bruit hors « fresh ». */
  dimStale: boolean
}

export const DrawingContext = createContext<DrawingContextValue | null>(null)

/** Objets d'une couche + helpers de sélection + projection. */
export function useDrawingLayer(layer: IntelligenceLayerKey) {
  const ctx = useContext(DrawingContext)
  const proj = useChartProjection()
  const objects = ctx ? ctx.objects.filter((o) => intelligenceLayerOf(o) === layer) : []
  return {
    proj,
    objects,
    asOf: ctx?.asOf ?? null,
    isSelected: (o: IntelligenceObject) => ctx?.selectedKey === selectionKeyOf(o),
    select: (o: IntelligenceObject) => ctx?.onSelect(selectionKeyOf(o)),
    isFresh: (o: IntelligenceObject) => ctx?.freshKeys.has(selectionKeyOf(o)) ?? false,
    dimStale: ctx?.dimStale ?? false,
  }
}

export type DrawTone = 'bull' | 'bear' | 'fib' | 'conf' | 'liq' | 'muted'

/** Estimation largeur texte (DM Mono 10px ≈ 6.1 px / caractère). */
export function textWidth(text: string, px = 10): number {
  return Math.ceil(text.length * px * 0.61)
}

/** Bord droit des objets vivants (as_of) — borné à la zone visible. */
export function rightEdge(proj: ChartProjection, t: number | null | undefined): number {
  const x = t == null ? null : proj.x(t)
  if (x == null) return proj.width
  return Math.min(proj.width, x + proj.barSpacing / 2)
}

/* ------------------------------------------------------------------ */
/* Étiquettes de la gouttière droite (objets vivants à as_of)          */
/* ------------------------------------------------------------------ */

export interface GutterEntry {
  id: string
  selKey: string
  /** Y d'ancrage (px) sur la forme. */
  y: number
  /** X d'où part le trait de rappel (bord droit de la forme). */
  fromX: number
  text: string
  /** Version courte (petits écrans). */
  short: string
  tone: DrawTone
}

/** En dessous de cette largeur de tracé, étiquettes courtes (mobile). */
export const COMPACT_WIDTH = 600

const mid = (o: IntelligenceObject) =>
  o.price_low != null && o.price_high != null ? (o.price_low + o.price_high) / 2 : null

/**
 * Libellés affichés à droite du dernier prix. Uniquement de la mise en forme
 * de champs Python (prix, touches, statut, confidence).
 */
export function gutterEntries(
  objects: IntelligenceObject[],
  proj: ChartProjection,
  asOf: number | null,
): GutterEntry[] {
  const edge = rightEdge(proj, asOf)
  const out: GutterEntry[] = []
  const push = (o: IntelligenceObject, price: number | null, text: string, short: string, tone: DrawTone) => {
    const y = price == null ? null : proj.y(price)
    if (y == null || y < 0 || y > proj.height) return
    out.push({ id: o.id, selKey: selectionKeyOf(o), y, fromX: edge, text, short, tone })
  }
  for (const o of objects) {
    const layer = intelligenceLayerOf(o)
    const status = o.origin.status
    if (layer === 'support_resistance') {
      const sup = o.side !== 'resistance'
      const htf = o.origin.htf ? ` ${String(o.origin.htf).toUpperCase()}` : ''
      const touches = o.origin.touch_count ? ` · ${o.origin.touch_count} touches` : ''
      const m = mid(o)
      push(
        o,
        m,
        `${sup ? 'SUPPORT' : 'RESISTANCE'}${htf} ${fmtPrice(m)}${touches} · ${fmtPct(o.confidence)}`,
        `${sup ? 'S' : 'R'}${htf} ${fmtPrice(m)}`,
        sup ? 'bull' : 'bear',
      )
    } else if (layer === 'fvg') {
      if (status === 'filled' || status === 'invalidated') continue
      const bear = o.origin.direction === 'bearish'
      push(o, mid(o), `${bear ? 'Bearish' : 'Bullish'} FVG · ${STATUS_LABELS[status ?? 'open']}`, `FVG${bear ? '↓' : '↑'}`, bear ? 'bear' : 'bull')
    } else if (layer === 'confluence') {
      push(o, mid(o), `CONFLUENCE ${fmtPct(o.confidence)}${o.origin.score_is_mock ? ' (mock)' : ''}`, `CONF ${fmtPct(o.confidence)}`, 'conf')
    } else if (layer === 'fibonacci') {
      const p = o.points[0]?.price ?? null
      const r = o.origin.ratio ?? Number(o.label)
      const pct = (r * 100).toFixed(r === 0 || r === 1 || r === 0.5 ? 0 : 1)
      push(o, p, `${pct} · ${fmtPrice(p)}`, pct, 'fib')
    } else if (layer === 'trendlines' && o.points.length >= 2) {
      const [p0, p1] = o.points as [{ time: number; price: number }, { time: number; price: number }]
      const x0 = proj.x(p0.time)
      const x1 = proj.x(p1.time)
      if (x0 == null || x1 == null || x1 === x0) continue
      // Prix de la droite au bord as_of, par proportion en pixels (affichage).
      const y0 = proj.y(p0.price)
      const y1 = proj.y(p1.price)
      if (y0 == null || y1 == null) continue
      const y = o.type === 'ray' ? y0 + ((y1 - y0) * (edge - x0)) / (x1 - x0) : y1
      if (y < 0 || y > proj.height) continue
      out.push({
        id: o.id,
        selKey: selectionKeyOf(o),
        y,
        fromX: edge,
        text: `TRENDLINE · ${fmtPct(o.confidence)}`,
        short: 'TL',
        tone: o.side === 'resistance' ? 'bear' : 'bull',
      })
    }
  }
  return out
}

/** Empile les étiquettes sans chevauchement (tri par Y, poussée vers le bas puis recentrage). */
export function layoutGutter(entries: GutterEntry[], height: number, rowH = 17): Array<GutterEntry & { ly: number }> {
  const sorted = [...entries].sort((a, b) => a.y - b.y)
  const placed: Array<GutterEntry & { ly: number }> = []
  let cursor = -Infinity
  for (const e of sorted) {
    const ly = Math.max(e.y, cursor + rowH)
    placed.push({ ...e, ly })
    cursor = ly
  }
  const overflow = cursor + rowH / 2 - height
  if (overflow > 0) for (const p of placed) p.ly -= overflow
  let floor = rowH / 2
  for (const p of placed) {
    p.ly = Math.max(p.ly, floor)
    floor = p.ly + rowH
  }
  return placed
}
