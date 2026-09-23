/** Client for GET /api/engine/chart-objects/{symbol} (T2a ChartObject). */

export type ChartObjectType =
  | 'horizontal_line'
  | 'trend_line'
  | 'ray'
  | 'zone'
  | 'rectangle'
  | 'channel'
  | 'marker'
  | 'text'
  | 'entry'
  | 'stop'
  | 'target'

export type ChartObjectSource = 'user' | 'engine' | 'claude' | 'strategy' | 'backtest'

export interface ChartPoint {
  time: number
  price: number
}

export interface ChartObject {
  id: string
  type: ChartObjectType
  source: ChartObjectSource
  symbol: string
  timeframe: string
  points: ChartPoint[]
  price_low: number | null
  price_high: number | null
  side: string | null
  label: string | null
  confidence: number
  as_of: number
  origin: Record<string, unknown>
  subtype: string | null
}

export interface ChartObjectsResponse {
  symbol: string
  timeframe: string
  as_of: number | null
  objects: ChartObject[]
  sources?: string[]
  count?: number
  provider?: string | null
  provider_symbol?: string | null
}

/** Fetch ENGINE chart objects for the Structure layer (zones / trendlines / markers). */
export async function getChartObjects(
  symbol: string,
  timeframe: string,
  limit = 300,
  sources: ChartObjectSource[] = ['engine'],
): Promise<ChartObject[]> {
  const q = new URLSearchParams({
    timeframe,
    limit: String(limit),
    sources: sources.join(','),
  })
  const res = await fetch(`/api/engine/chart-objects/${encodeURIComponent(symbol)}?${q}`, {
    credentials: 'include',
  })
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { detail?: string } | null
    throw new Error(body?.detail ?? `Erreur ${res.status}`)
  }
  const data = (await res.json()) as ChartObjectsResponse
  return data.objects ?? []
}

/** Zones usable by PriceChart (visual parity with former StructureOverlay.zones). */
export function chartObjectZones(objects: ChartObject[]): Array<{
  side: 'support' | 'resistance'
  low: number
  high: number
  touch_count: number
  label: string
}> {
  return objects
    .filter((o) => o.type === 'zone' && o.price_low != null && o.price_high != null)
    .map((o) => ({
      side: (o.side === 'resistance' ? 'resistance' : 'support') as 'support' | 'resistance',
      low: o.price_low as number,
      high: o.price_high as number,
      touch_count: Number(o.origin?.touch_count ?? 0),
      label: o.label ?? '',
    }))
}

/** Trendlines usable by PriceChart (visual parity with StructureOverlay.trendlines). */
export function chartObjectTrendlines(objects: ChartObject[]): Array<{
  side: 'support' | 'resistance'
  start_time: number
  end_time: number
  start_price: number
  end_price: number
}> {
  return objects
    .filter((o) => o.type === 'trend_line' && o.points.length === 2)
    .map((o) => ({
      side: (o.side === 'resistance' ? 'resistance' : 'support') as 'support' | 'resistance',
      start_time: o.points[0]!.time,
      end_time: o.points[1]!.time,
      start_price: o.points[0]!.price,
      end_price: o.points[1]!.price,
    }))
}

/** Breakout (and other) markers — one point each. */
export function chartObjectMarkers(objects: ChartObject[]): Array<{
  time: number
  price: number
  side: string | null
  label: string
  confirmed: boolean
}> {
  return objects
    .filter((o) => o.type === 'marker' && o.points.length === 1)
    .map((o) => ({
      time: o.points[0]!.time,
      price: o.points[0]!.price,
      side: o.side,
      label: o.label ?? 'BO',
      confirmed: Boolean(o.origin?.confirmed ?? true),
    }))
}
