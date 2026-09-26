/**
 * Hook Chart Intelligence : chargement (mock | API Python), replay as_of,
 * sélection d'objet, visibilité des couches.
 *
 * Aucune logique financière : le hook demande un snapshot « as_of » et
 * affiche ce que la source renvoie. L'anti-lookahead est la responsabilité
 * de la source (Python — ici simulé par chartIntelligenceMock).
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  DEFAULT_INTELLIGENCE_LAYERS,
  getChartIntelligence,
  intelligenceLayerOf,
  selectionKeyOf,
  type ChartIntelligenceResponse,
  type IntelligenceLayerKey,
  type IntelligenceLayerPrefs,
  type IntelligenceObject,
} from './chartIntelligence'
import { mockChartIntelligenceAt } from './chartIntelligenceMock'

export type ChartIntelligenceSource = 'mock' | 'api'

export interface UseChartIntelligenceOptions {
  symbol: string
  timeframe: string
  /** 'mock' tant que l'endpoint Python n'existe pas. */
  source?: ChartIntelligenceSource
  /** Vitesse du replay (ms par bougie). */
  replayIntervalMs?: number
}

const LAYERS_KEY = 'ichivol.chart-intelligence.layers.v1'

function loadLayers(): IntelligenceLayerPrefs {
  try {
    const raw = localStorage.getItem(LAYERS_KEY)
    if (!raw) return DEFAULT_INTELLIGENCE_LAYERS
    return { ...DEFAULT_INTELLIGENCE_LAYERS, ...(JSON.parse(raw) as Partial<IntelligenceLayerPrefs>) }
  } catch {
    return DEFAULT_INTELLIGENCE_LAYERS
  }
}

function saveLayers(prefs: IntelligenceLayerPrefs) {
  try {
    localStorage.setItem(LAYERS_KEY, JSON.stringify(prefs))
  } catch {
    /* ignore */
  }
}

async function fetchSnapshot(
  source: ChartIntelligenceSource,
  symbol: string,
  timeframe: string,
  asOf: number | null,
): Promise<ChartIntelligenceResponse> {
  if (source === 'api') return getChartIntelligence({ symbol, timeframe, asOf })
  return mockChartIntelligenceAt(asOf ?? undefined)
}

export function useChartIntelligence({
  symbol,
  timeframe,
  source = 'mock',
  replayIntervalMs = 450,
}: UseChartIntelligenceOptions) {
  /** null = live (dernière bougie). */
  const [asOf, setAsOf] = useState<number | null>(null)
  const [playing, setPlaying] = useState(false)
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [layers, setLayersState] = useState<IntelligenceLayerPrefs>(loadLayers)
  /** Dernier résultat reçu, étiqueté par la requête qui l'a produit. */
  const [result, setResult] = useState<{
    key: string
    response: ChartIntelligenceResponse | null
    error: string | null
  }>({ key: '', response: null, error: null })
  /** Bornes de replay conservées d'une réponse à l'autre. */
  const [bounds, setBounds] = useState<ChartIntelligenceResponse['replay'] | null>(null)

  const requestKey = `${source}|${symbol}|${timeframe}|${asOf ?? 'live'}`
  const loading = result.key !== requestKey

  useEffect(() => {
    let cancelled = false
    fetchSnapshot(source, symbol, timeframe, asOf)
      .then((res) => {
        if (cancelled) return
        if (res.replay) setBounds(res.replay)
        setResult({ key: requestKey, response: res, error: null })
      })
      .catch((e: unknown) => {
        if (cancelled) return
        setResult((prev) => ({
          key: requestKey,
          response: prev.response,
          error: e instanceof Error ? e.message : 'Chart Intelligence indisponible',
        }))
        setPlaying(false)
      })
    return () => {
      cancelled = true
    }
  }, [source, symbol, timeframe, asOf, requestKey])

  const response = result.response
  const error = result.error
  const cursor = asOf ?? response?.as_of ?? null

  const step = useCallback(
    (dir: 1 | -1) => {
      if (!bounds || cursor == null) return
      const next = cursor + dir * bounds.bar_seconds
      if (next >= bounds.last) {
        setAsOf(null)
        setPlaying(false)
        return
      }
      setAsOf(Math.max(bounds.first, next))
    },
    [bounds, cursor],
  )

  const seek = useCallback(
    (t: number | null) => {
      if (t == null || !bounds || t >= bounds.last) setAsOf(null)
      else setAsOf(Math.max(bounds.first, t))
    },
    [bounds],
  )

  const play = useCallback(() => {
    if (!bounds) return
    // Relance depuis le début si on est déjà au live.
    if (asOf == null) setAsOf(bounds.first)
    setPlaying(true)
  }, [asOf, bounds])

  const pause = useCallback(() => setPlaying(false), [])

  useEffect(() => {
    if (!playing || loading) return
    const id = window.setTimeout(() => step(1), replayIntervalMs)
    return () => window.clearTimeout(id)
  }, [playing, loading, step, replayIntervalMs, cursor])

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

  /** Objets de la sélection courante (plusieurs pour un Fib groupé). */
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
    counts,
    layers,
    setLayers,
    toggleLayer,
    // Un objet pas encore connu à as_of n'est pas sélectionnable (replay).
    selectedKey: selection.length ? selectedKey : null,
    select: setSelectedKey,
    selection,
    replay: {
      asOf: cursor,
      isLive: asOf == null,
      bounds,
      playing,
      play,
      pause,
      step,
      seek,
    },
  }
}

export type ChartIntelligenceState = ReturnType<typeof useChartIntelligence>
