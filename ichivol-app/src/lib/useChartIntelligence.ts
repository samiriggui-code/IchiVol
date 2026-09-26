/**
 * Hook Chart Intelligence : charge UN snapshot live, puis replay progressif
 * côté client (filtre as_of) — sans re-fetch à chaque bougie.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  DEFAULT_INTELLIGENCE_LAYERS,
  getChartIntelligence,
  intelligenceLayerOf,
  objectKnownAt,
  selectionKeyOf,
  sliceIntelligenceAt,
  type ChartIntelligenceResponse,
  type IntelligenceLayerKey,
  type IntelligenceLayerPrefs,
  type IntelligenceObject,
} from './chartIntelligence'
import { mockChartIntelligenceAt } from './chartIntelligenceMock'

export type ChartIntelligenceSource = 'mock' | 'api'

export type ReplaySpeed = 0.5 | 1 | 2

export interface UseChartIntelligenceOptions {
  symbol: string
  timeframe: string
  source?: ChartIntelligenceSource
  /** ms de base pour 1× (ralenti volontairement pour suivre l’évolution). */
  replayIntervalMs?: number
  /** Nombre de bougies avant la fin pour démarrer PLAY (fenêtre récente). */
  playLookbackBars?: number
}

const LAYERS_KEY = 'ichivol.chart-intelligence.layers.v1'
/** Fenêtre de départ du PLAY — assez courte pour suivre sans polluer. */
const DEFAULT_PLAY_LOOKBACK = 48

function loadLayers(): IntelligenceLayerPrefs {
  try {
    const raw = localStorage.getItem(LAYERS_KEY)
    if (!raw) return { ...DEFAULT_INTELLIGENCE_LAYERS }
    // Merge : nouvelles clés (ex. calques off par défaut) gagnent si absentes du storage.
    return { ...DEFAULT_INTELLIGENCE_LAYERS, ...(JSON.parse(raw) as Partial<IntelligenceLayerPrefs>) }
  } catch {
    return { ...DEFAULT_INTELLIGENCE_LAYERS }
  }
}

function saveLayers(prefs: IntelligenceLayerPrefs) {
  try {
    localStorage.setItem(LAYERS_KEY, JSON.stringify(prefs))
  } catch {
    /* ignore */
  }
}

async function fetchLive(
  source: ChartIntelligenceSource,
  symbol: string,
  timeframe: string,
): Promise<ChartIntelligenceResponse> {
  if (source === 'api') return getChartIntelligence({ symbol, timeframe, asOf: null })
  return mockChartIntelligenceAt()
}

export function useChartIntelligence({
  symbol,
  timeframe,
  source = 'api',
  replayIntervalMs = 900,
  playLookbackBars = DEFAULT_PLAY_LOOKBACK,
}: UseChartIntelligenceOptions) {
  /** null = live (dernière bougie). */
  const [asOf, setAsOf] = useState<number | null>(null)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState<ReplaySpeed>(1)
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [layers, setLayersState] = useState<IntelligenceLayerPrefs>(loadLayers)
  const [live, setLive] = useState<ChartIntelligenceResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const liveKey = `${source}|${symbol}|${timeframe}`

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setAsOf(null)
    setPlaying(false)
    setSelectedKey(null)
    fetchLive(source, symbol, timeframe)
      .then((res) => {
        if (cancelled) return
        setLive(res)
        setLoading(false)
      })
      .catch((e: unknown) => {
        if (cancelled) return
        setLive(null)
        setLoading(false)
        setError(e instanceof Error ? e.message : 'Chart Intelligence indisponible')
        setPlaying(false)
      })
    return () => {
      cancelled = true
    }
  }, [source, symbol, timeframe, liveKey])

  const bounds = live?.replay ?? null
  const liveAsOf = live?.as_of ?? null
  const cursor = asOf ?? liveAsOf

  const response = useMemo(() => {
    if (!live) return null
    if (asOf == null) return live
    return sliceIntelligenceAt(live, asOf)
  }, [live, asOf])

  const step = useCallback(
    (dir: 1 | -1) => {
      if (!bounds || cursor == null) return
      const next = cursor + dir * bounds.bar_seconds
      if (next >= bounds.last) {
        setAsOf(null)
        setPlaying(false)
        return
      }
      if (next <= bounds.first) {
        setAsOf(bounds.first)
        return
      }
      setAsOf(next)
    },
    [bounds, cursor],
  )

  const seek = useCallback(
    (t: number | null) => {
      if (t == null || !bounds || t >= bounds.last) {
        setAsOf(null)
        setPlaying(false)
        return
      }
      setAsOf(Math.max(bounds.first, t))
    },
    [bounds],
  )

  const play = useCallback(() => {
    if (!bounds || liveAsOf == null) return
    // Départ sur une fenêtre récente — pas depuis le début de l’historique.
    if (asOf == null || asOf >= bounds.last) {
      const lookback = Math.max(8, playLookbackBars) * bounds.bar_seconds
      const start = Math.max(bounds.first, liveAsOf - lookback)
      setAsOf(start)
    }
    setPlaying(true)
  }, [asOf, bounds, liveAsOf, playLookbackBars])

  const pause = useCallback(() => setPlaying(false), [])

  const intervalMs = Math.round(replayIntervalMs / speed)

  useEffect(() => {
    if (!playing || loading || !live) return
    const id = window.setTimeout(() => step(1), intervalMs)
    return () => window.clearTimeout(id)
  }, [playing, loading, live, step, intervalMs, cursor])

  const setLayers = useCallback((next: IntelligenceLayerPrefs) => {
    setLayersState(next)
    saveLayers(next)
  }, [])

  const toggleLayer = useCallback(
    (key: IntelligenceLayerKey) => setLayers({ ...layers, [key]: !layers[key] }),
    [layers, setLayers],
  )

  const objects = useMemo(() => response?.objects ?? [], [response])

  const visibleObjects = useMemo(
    () => objects.filter((o) => layers[intelligenceLayerOf(o)]),
    [objects, layers],
  )

  /** Objets apparus sur la dernière bougie du curseur (révélation progressive). */
  const freshKeys = useMemo(() => {
    if (cursor == null || !bounds) return new Set<string>()
    const prev = cursor - bounds.bar_seconds
    const keys = new Set<string>()
    for (const o of objects) {
      const known = objectKnownAt(o)
      if (known > prev && known <= cursor) keys.add(selectionKeyOf(o))
    }
    return keys
  }, [objects, cursor, bounds])

  const counts = useMemo(() => {
    const c = Object.fromEntries(
      Object.keys(DEFAULT_INTELLIGENCE_LAYERS).map((k) => [k, 0]),
    ) as Record<IntelligenceLayerKey, number>
    const seen = new Set<string>()
    for (const o of objects) {
      const key = selectionKeyOf(o)
      if (seen.has(key)) continue
      seen.add(key)
      c[intelligenceLayerOf(o)] += 1
    }
    return c
  }, [objects])

  const selection = useMemo<IntelligenceObject[]>(
    () => (selectedKey ? objects.filter((o) => selectionKeyOf(o) === selectedKey) : []),
    [objects, selectedKey],
  )

  return {
    response,
    loading,
    error,
    objects,
    visibleObjects,
    freshKeys,
    counts,
    layers,
    setLayers,
    toggleLayer,
    selectedKey: selection.length ? selectedKey : null,
    select: setSelectedKey,
    selection,
    replay: {
      asOf: cursor,
      isLive: asOf == null,
      bounds,
      playing,
      speed,
      setSpeed,
      play,
      pause,
      step,
      seek,
    },
  }
}

export type ChartIntelligenceState = ReturnType<typeof useChartIntelligence>
