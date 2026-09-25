/** Seuils RVOL/ATR envoyés au moteur (query params). */

import { getSettings } from './settings'
import type { VolumeParams } from './types'

export interface EngineThresholds {
  rvolLow: number
  rvolSignificant: number
  rvolStrong: number
  rvolAnomaly: number
  atrDeadPercentile: number
  atrExtremePercentile: number
  atrStopMultiplier: number
}

/** Défauts alignés sur engine/README.md */
export const DEFAULT_ENGINE_THRESHOLDS: EngineThresholds = {
  rvolLow: 0.7,
  rvolSignificant: 1.5,
  rvolStrong: 2.0,
  rvolAnomaly: 3.0,
  atrDeadPercentile: 0.15,
  atrExtremePercentile: 0.9,
  atrStopMultiplier: 1.5,
}

const QUERY_KEYS: Record<keyof EngineThresholds, string> = {
  rvolLow: 'rvol_low',
  rvolSignificant: 'rvol_significant',
  rvolStrong: 'rvol_strong',
  rvolAnomaly: 'rvol_anomaly',
  atrDeadPercentile: 'atr_dead_percentile',
  atrExtremePercentile: 'atr_extreme_percentile',
  atrStopMultiplier: 'atr_stop_multiplier',
}

let cache: EngineThresholds | null = null

export function thresholdsFromVolume(vol: Partial<VolumeParams> | undefined): EngineThresholds {
  const d = DEFAULT_ENGINE_THRESHOLDS
  return {
    rvolLow: vol?.rvolLow ?? d.rvolLow,
    rvolSignificant: vol?.rvolSignificant ?? vol?.rvolConfirm ?? d.rvolSignificant,
    rvolStrong: vol?.rvolStrong ?? d.rvolStrong,
    rvolAnomaly: vol?.rvolAnomaly ?? d.rvolAnomaly,
    atrDeadPercentile: vol?.atrDeadPercentile ?? d.atrDeadPercentile,
    atrExtremePercentile: vol?.atrExtremePercentile ?? d.atrExtremePercentile,
    atrStopMultiplier: vol?.atrStopMultiplier ?? d.atrStopMultiplier,
  }
}

export function invalidateEngineThresholdsCache(): void {
  cache = null
}

export async function loadEngineThresholds(): Promise<EngineThresholds> {
  if (cache) return cache
  try {
    const s = await getSettings()
    cache = thresholdsFromVolume(s.volumeParams)
  } catch {
    cache = { ...DEFAULT_ENGINE_THRESHOLDS }
  }
  return cache
}

export function appendEngineThresholds(
  params: URLSearchParams,
  t: EngineThresholds = DEFAULT_ENGINE_THRESHOLDS,
): void {
  // N’envoyer que les overrides : sinon le moteur bypass le cache screener
  // (scan live de toute la watchlist) et le proxy Express abort à 45s.
  const d = DEFAULT_ENGINE_THRESHOLDS
  for (const key of Object.keys(QUERY_KEYS) as (keyof EngineThresholds)[]) {
    if (t[key] !== d[key]) {
      params.set(QUERY_KEYS[key], String(t[key]))
    }
  }
}

/** True si au moins un seuil diffère des défauts moteur (scan live, pas de cache). */
export function hasCustomEngineThresholds(t: EngineThresholds): boolean {
  const d = DEFAULT_ENGINE_THRESHOLDS
  return (Object.keys(QUERY_KEYS) as (keyof EngineThresholds)[]).some((k) => t[k] !== d[k])
}

/** Validate order client-side before save (mirrors engine 422). */
export function validateEngineThresholds(t: EngineThresholds): string | null {
  if (!(t.rvolLow < t.rvolSignificant && t.rvolSignificant < t.rvolStrong && t.rvolStrong < t.rvolAnomaly)) {
    return 'RVOL : attendu low < significant < strong < anomaly'
  }
  if (!(0 <= t.atrDeadPercentile && t.atrDeadPercentile < t.atrExtremePercentile && t.atrExtremePercentile <= 1)) {
    return 'ATR : attendu 0 ≤ dead < extreme ≤ 1'
  }
  if (!(t.atrStopMultiplier > 0)) {
    return 'ATR stop multiplier doit être > 0'
  }
  return null
}
