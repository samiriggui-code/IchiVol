/**
 * Projection temps/prix → pixels partagée entre IntelligenceChart (lightweight-charts)
 * et les couches SVG React (DrawingLayer et enfants).
 */

import { createContext, useContext } from 'react'

export interface ChartProjection {
  /** Coordonnée X d'un temps unix (s). Fonctionne aussi au-delà de la dernière bougie. */
  x: (time: number) => number | null
  /** Coordonnée Y d'un prix sur l'échelle des bougies. */
  y: (price: number) => number | null
  /** Largeur de la zone de tracé (hors échelle de prix). */
  width: number
  height: number
  /** Espacement entre deux bougies (px). */
  barSpacing: number
  /** Incrémenté à chaque pan / zoom / resize → force le re-rendu des couches. */
  rev: number
}

export const ChartProjectionContext = createContext<ChartProjection | null>(null)

export function useChartProjection(): ChartProjection | null {
  return useContext(ChartProjectionContext)
}
