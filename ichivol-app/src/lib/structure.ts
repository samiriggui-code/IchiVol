/** Client pour GET /api/engine/structure/{symbol} : zones S/R + trendlines du moteur. */

export interface StructureZone {
  side: 'support' | 'resistance'
  low: number
  high: number
  mid: number
  score: number
  touch_count: number
}

export interface StructureTrendline {
  side: 'support' | 'resistance'
  score: number
  touch_count: number
  source: string
  start_time?: number
  end_time?: number
  start_price?: number
  end_price?: number
}

export interface EngineStructure {
  consensus: {
    structure_score: number
    support_zones: StructureZone[]
    resistance_zones: StructureZone[]
  }
  detectors: Record<
    string,
    {
      support_trendlines: StructureTrendline[]
      resistance_trendlines: StructureTrendline[]
    }
  >
}

export interface StructureOverlay {
  zones: StructureZone[]
  trendlines: Required<StructureTrendline>[]
}

const MAX_ZONES_PER_SIDE = 3
const MAX_TRENDLINES_PER_SIDE = 2

function hasPoints(t: StructureTrendline): t is Required<StructureTrendline> {
  return (
    t.start_time != null &&
    t.end_time != null &&
    t.start_price != null &&
    t.end_price != null &&
    t.end_time > t.start_time
  )
}

function topByScore<T extends { score: number }>(rows: T[], n: number): T[] {
  return [...rows].sort((a, b) => b.score - a.score).slice(0, n)
}

/** Ne garde que le signal utile : les meilleures zones/lignes, pas tout le bruit des détecteurs. */
export function toStructureOverlay(s: EngineStructure): StructureOverlay {
  const zones = [
    ...topByScore(s.consensus.support_zones, MAX_ZONES_PER_SIDE),
    ...topByScore(s.consensus.resistance_zones, MAX_ZONES_PER_SIDE),
  ]
  const all = Object.values(s.detectors).flatMap((d) => [
    ...d.support_trendlines,
    ...d.resistance_trendlines,
  ])
  const drawable = all.filter(hasPoints)
  const trendlines = [
    ...topByScore(drawable.filter((t) => t.side === 'support'), MAX_TRENDLINES_PER_SIDE),
    ...topByScore(drawable.filter((t) => t.side === 'resistance'), MAX_TRENDLINES_PER_SIDE),
  ]
  return { zones, trendlines }
}

export async function getEngineStructure(
  symbol: string,
  timeframe: string,
  limit = 300,
): Promise<StructureOverlay> {
  const q = new URLSearchParams({ timeframe, limit: String(limit) })
  const res = await fetch(`/api/engine/structure/${encodeURIComponent(symbol)}?${q}`, {
    credentials: 'include',
  })
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { detail?: string } | null
    throw new Error(body?.detail ?? `Erreur ${res.status}`)
  }
  return toStructureOverlay((await res.json()) as EngineStructure)
}
