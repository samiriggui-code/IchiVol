/**
 * Chart Intelligence Briefing — période + packs calques + caméra.
 *
 * V0 = directeur heuristique (context → défauts). Eve pourra proposer plus tard ;
 * le moteur valide les objets (ChartObject), l’humain confirme. Aucun niveau inventé.
 *
 * Placement : fiches Décisions (`prep`) / Position (`position`) uniquement —
 * pas le graphique Marché (PriceChart).
 */

import {
  DEFAULT_INTELLIGENCE_LAYERS,
  type IntelligenceLayerPrefs,
} from './chartIntelligence'

/* ------------------------------------------------------------------ */
/* Période (fenêtre visible, pas le timeframe API)                     */
/* ------------------------------------------------------------------ */

export type BriefingPeriodId = 'focus' | 'setup' | 'swing' | 'full'

export interface BriefingPeriod {
  id: BriefingPeriodId
  label: string
  /** Nombre de bougies visibles depuis la droite ; null = tout (fit). */
  bars: number | null
  hint: string
}

export const BRIEFING_PERIODS: BriefingPeriod[] = [
  { id: 'focus', label: 'Focus', bars: 24, hint: '~1 j en 1H' },
  { id: 'setup', label: 'Setup', bars: 48, hint: 'fenêtre récente' },
  { id: 'swing', label: 'Swing', bars: 120, hint: '~5 j en 1H' },
  { id: 'full', label: 'Tout', bars: null, hint: 'historique chargé' },
]

/* ------------------------------------------------------------------ */
/* Packs calques (presets d’affichage — pas de nouveaux objets)        */
/* ------------------------------------------------------------------ */

export type LayerPackId = 'calm' | 'structure' | 'setup' | 'liquidity' | 'full'

export interface LayerPack {
  id: LayerPackId
  label: string
  hint: string
  layers: IntelligenceLayerPrefs
}

const off = { ...DEFAULT_INTELLIGENCE_LAYERS, ...Object.fromEntries(
  (Object.keys(DEFAULT_INTELLIGENCE_LAYERS) as (keyof IntelligenceLayerPrefs)[]).map((k) => [k, false]),
) } as IntelligenceLayerPrefs

export const LAYER_PACKS: LayerPack[] = [
  {
    id: 'calm',
    label: 'Calme',
    hint: 'Ichimoku + structure',
    layers: { ...off, ichimoku: true, market_structure: true },
  },
  {
    id: 'structure',
    label: 'Structure',
    hint: '+ S/R',
    layers: { ...off, ichimoku: true, market_structure: true, support_resistance: true },
  },
  {
    id: 'setup',
    label: 'Setup',
    hint: 'Fib + FVG + structure',
    layers: {
      ...off,
      ichimoku: true,
      market_structure: true,
      fibonacci: true,
      fvg: true,
    },
  },
  {
    id: 'liquidity',
    label: 'Liquidité',
    hint: 'BSL/SSL + S/R',
    layers: {
      ...off,
      ichimoku: true,
      market_structure: true,
      support_resistance: true,
      liquidity: true,
    },
  },
  {
    id: 'full',
    label: 'Tout',
    hint: 'tous les calques',
    layers: {
      market_structure: true,
      support_resistance: true,
      trendlines: true,
      fibonacci: true,
      fvg: true,
      liquidity: true,
      ichimoku: true,
      confluence: true,
    },
  },
]

export function packById(id: LayerPackId): LayerPack {
  return LAYER_PACKS.find((p) => p.id === id) ?? LAYER_PACKS[0]!
}

export function periodById(id: BriefingPeriodId): BriefingPeriod {
  return BRIEFING_PERIODS.find((p) => p.id === id) ?? BRIEFING_PERIODS[1]!
}

/** Pack actif si les prefs matchent exactement un preset ; sinon null (perso). */
export function matchLayerPack(prefs: IntelligenceLayerPrefs): LayerPackId | null {
  for (const pack of LAYER_PACKS) {
    const keys = Object.keys(pack.layers) as (keyof IntelligenceLayerPrefs)[]
    if (keys.every((k) => prefs[k] === pack.layers[k])) return pack.id
  }
  return null
}

/* ------------------------------------------------------------------ */
/* Caméra                                                              */
/* ------------------------------------------------------------------ */

export type CameraMode = 'follow' | 'fit' | 'manual'

/**
 * Contrat caméra pour IntelligenceChart.
 * `token` force un re-cadrage (changement de période / reset symbole).
 */
export interface ChartCamera {
  mode: CameraMode
  /** Bougies visibles (follow) ; null si fit / full. */
  visibleBars: number | null
  token: number
}

export function cameraForPeriod(period: BriefingPeriodId, token: number): ChartCamera {
  const p = periodById(period)
  if (p.bars == null) return { mode: 'fit', visibleBars: null, token }
  return { mode: 'follow', visibleBars: p.bars, token }
}

/* ------------------------------------------------------------------ */
/* Directeur heuristique V0 (Eve plus tard)                            */
/* ------------------------------------------------------------------ */

export type BriefingContext = 'prep' | 'position' | 'explore'

export interface BriefingDefaults {
  period: BriefingPeriodId
  pack: LayerPackId
}

/**
 * Défauts selon le contexte d’usage (fiche Décisions / Position / explore).
 * Heuristique produit V0 — pas un LLM, pas un vote pipeline.
 */
export function defaultBriefing(context: BriefingContext): BriefingDefaults {
  if (context === 'prep') return { period: 'setup', pack: 'setup' }
  if (context === 'position') return { period: 'swing', pack: 'structure' }
  return { period: 'setup', pack: 'calm' }
}
