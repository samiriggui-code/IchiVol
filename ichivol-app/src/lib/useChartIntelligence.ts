/**
 * Hook Chart Intelligence : snapshot live + replay walk-forward (CI-R1a).
 *
 * Prod API : PLAY charge `/chart-intelligence/{symbol}/replay` (objets
 * recalculés bougie par bougie). On ne rejoue plus un snapshot live via
 * `sliceIntelligenceAt` sur les objets (lookahead).
 * Mock : conserve le slice client (données déjà datées correctement).
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  DEFAULT_INTELLIGENCE_LAYERS,
  getChartIntelligence,
  getChartIntelligenceReplay,
  intelligenceLayerOf,
  objectKnownAt,
  selectionKeyOf,
  sliceIntelligenceAt,
  type ChartIntelligenceReplayFrame,
  type ChartIntelligenceReplayPack,
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

function frameToResponse(
  series: ChartIntelligenceResponse,
  frame: ChartIntelligenceReplayFrame,
): ChartIntelligenceResponse {
  // CI-R7: series once at pack/live root; truncate by as_of (objects from walk-forward).
  const barSec = series.replay?.bar_seconds ?? 3600
  const asOf = frame.as_of
  return {
    ...series,
    as_of: asOf,
    candles: series.candles.filter((c) => c.time <= asOf),
    ichimoku: series.ichimoku.filter((p) => p.time <= asOf),
    projection: series.projection.filter((p) => p.time - 25 * barSec <= asOf),
    objects: frame.objects,
    count: frame.objects.length,
    market_state: frame.market_state,
    analysis: null, // pas de spoiler pendant replay
  }
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
  const [replayPack, setReplayPack] = useState<ChartIntelligenceReplayPack | null>(null)
  const [replayLoading, setReplayLoading] = useState(false)
  const [replayError, setReplayError] = useState<string | null>(null)

  const liveKey = `${source}|${symbol}|${timeframe}`

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setAsOf(null)
    setPlaying(false)
    setSelectedKey(null)
    setReplayPack(null)
    setReplayError(null)
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

  const framesByAsOf = useMemo(() => {
    const m = new Map<number, ChartIntelligenceReplayFrame>()
    if (!replayPack?.frames) return m
    for (const f of replayPack.frames) m.set(f.as_of, f)
    return m
  }, [replayPack])

  const response = useMemo(() => {
    if (!live) return null
    if (asOf == null) return live
    // API prod : frame walk-forward uniquement (pas de slice objets live).
    if (source === 'api') {
      const frame = framesByAsOf.get(asOf)
      if (frame) {
        // Prefer pack root series (CI-R7) — same walk-forward window as objects.
        const series = (replayPack as ChartIntelligenceResponse | null) ?? live
        return frameToResponse(series, frame)
      }
      // Pas de frame → rester live (PLAY désactivé / pack absent).
      return live
    }
    // Mock : slice client (known_at déjà datés correctement dans le mock).
    return sliceIntelligenceAt(live, asOf)
  }, [live, asOf, source, framesByAsOf, replayPack])

  const ensureReplayPack = useCallback(async (): Promise<ChartIntelligenceReplayPack | null> => {
    if (source !== 'api') return null
    if (replayPack) return replayPack
    if (!live || liveAsOf == null || !bounds) return null
    setReplayLoading(true)
    setReplayError(null)
    try {
      const lookback = Math.max(8, playLookbackBars)
      const from = Math.max(bounds.first, liveAsOf - lookback * bounds.bar_seconds)
      const pack = await getChartIntelligenceReplay({
        symbol,
        timeframe,
        from,
        to: liveAsOf,
        lookbackBars: lookback,
      })
      setReplayPack(pack)
      setReplayLoading(false)
      return pack
    } catch (e: unknown) {
      setReplayLoading(false)
      setReplayError(e instanceof Error ? e.message : 'Replay indisponible')
      setPlaying(false)
      return null
    }
  }, [source, replayPack, live, liveAsOf, bounds, playLookbackBars, symbol, timeframe])

  const step = useCallback(
    (dir: 1 | -1) => {
      if (!bounds || cursor == null) return
      if (source === 'api' && replayPack?.frames?.length) {
        const times = replayPack.frames.map((f) => f.as_of)
        let idx = times.indexOf(cursor)
        if (idx < 0) {
          // Snap to nearest frame.
          idx = times.reduce((best, t, i) => (Math.abs(t - cursor) < Math.abs(times[best]! - cursor) ? i : best), 0)
        }
        const nextIdx = idx + dir
        if (nextIdx >= times.length) {
          setAsOf(null)
          setPlaying(false)
          return
        }
        if (nextIdx < 0) {
          setAsOf(times[0]!)
          return
        }
        setAsOf(times[nextIdx]!)
        return
      }
      if (source === 'api') return // pas de step sans pack
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
    [bounds, cursor, source, replayPack],
  )

  const seek = useCallback(
    (t: number | null) => {
      if (t == null || !bounds || t >= bounds.last) {
        setAsOf(null)
        setPlaying(false)
        return
      }
      if (source === 'api' && replayPack?.frames?.length) {
        const times = replayPack.frames.map((f) => f.as_of)
        const nearest = times.reduce((best, x) => (Math.abs(x - t) < Math.abs(best - t) ? x : best), times[0]!)
        setAsOf(nearest)
        return
      }
      if (source === 'api') return
      setAsOf(Math.max(bounds.first, t))
    },
    [bounds, source, replayPack],
  )

  const play = useCallback(async () => {
    if (!bounds || liveAsOf == null) return
    if (source === 'api') {
      const pack = await ensureReplayPack()
      if (!pack?.frames?.length) return
      if (asOf == null || asOf >= bounds.last || !pack.frames.some((f) => f.as_of === asOf)) {
        setAsOf(pack.frames[0]!.as_of)
      }
      setPlaying(true)
      return
    }
    if (asOf == null || asOf >= bounds.last) {
      const lookback = Math.max(8, playLookbackBars) * bounds.bar_seconds
      const start = Math.max(bounds.first, liveAsOf - lookback)
      setAsOf(start)
    }
    setPlaying(true)
  }, [asOf, bounds, liveAsOf, playLookbackBars, source, ensureReplayPack])

  const pause = useCallback(() => setPlaying(false), [])

  const intervalMs = Math.round(replayIntervalMs / speed)

  useEffect(() => {
    if (!playing || loading || !live) return
    if (source === 'api' && !replayPack?.frames?.length) return
    const id = window.setTimeout(() => step(1), intervalMs)
    return () => window.clearTimeout(id)
  }, [playing, loading, live, step, intervalMs, cursor, source, replayPack])

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

  /** API : PLAY utilisable seulement si le pack walk-forward est dispo (ou chargeable). */
  const replayReady = source === 'mock' || replayPack != null || (replayError == null && !replayLoading)
  const replayBlocked = source === 'api' && replayError != null && replayPack == null

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
      ready: replayReady,
      blocked: replayBlocked,
      loading: replayLoading,
      error: replayError,
      hasFrames: Boolean(replayPack?.frames?.length),
    },
  }
}

export type ChartIntelligenceState = ReturnType<typeof useChartIntelligence>
