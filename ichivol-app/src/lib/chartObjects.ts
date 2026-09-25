/** Client for GET/POST/DELETE /api/engine/chart-objects (T2a read + T2c USER write). */

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

export type ChartObjectLayer =
  | 'structure'
  | 'fibonacci'
  | 'fvg'
  | 'breaks'
  | 'claude'
  | 'user_trades'
  | 'backtest'

export type UserTradePointType = 'entry' | 'stop' | 'target'

export interface ChartPoint {
  time: number
  price: number
}

export interface ChartObject {
  id: string
  type: ChartObjectType
  source: ChartObjectSource
  /** UI layer — absent on older payloads → deduce from source. */
  layer?: ChartObjectLayer | null
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

export interface UserTradePointInput {
  type: UserTradePointType
  timeframe: string
  price: number
  time: number
  side?: 'LONG' | 'SHORT' | null
  label?: string | null
  setup_id?: string
  as_of?: number
  limit?: number
}

/** Fetch chart objects. Default includes ENGINE + persisted USER/CLAUDE (T2b). */
export async function getChartObjects(
  symbol: string,
  timeframe: string,
  limit = 300,
  sources: ChartObjectSource[] = ['engine', 'user', 'claude'],
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

/** Persist a USER ENTRY/STOP/TARGET (T2c unitary — prefer postUserTradeSetup). */
export async function postUserTradePoint(
  symbol: string,
  input: UserTradePointInput,
): Promise<ChartObject> {
  const res = await fetch(`/api/engine/chart-objects/${encodeURIComponent(symbol)}`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(input),
  })
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { detail?: string } | null
    throw new Error(body?.detail ?? `Erreur ${res.status}`)
  }
  const data = (await res.json()) as { object: ChartObject }
  return data.object
}

export interface UserTradeSetupInput {
  timeframe: string
  entry: ChartPoint
  stop: ChartPoint
  target: ChartPoint
  setup_id?: string
  limit?: number
}

export interface UserTradeSetupResult {
  setup_id: string
  direction: 'long' | 'short'
  upserted: boolean
  objects: ChartObject[]
}

/** Atomic USER setup: ENTRY+STOP+TARGET in one transaction (T2c). */
export async function postUserTradeSetup(
  symbol: string,
  input: UserTradeSetupInput,
): Promise<UserTradeSetupResult> {
  const res = await fetch(
    `/api/engine/chart-objects/${encodeURIComponent(symbol)}/setup`,
    {
      method: 'POST',
      credentials: 'include',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(input),
    },
  )
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { detail?: string } | null
    throw new Error(body?.detail ?? `Erreur ${res.status}`)
  }
  return (await res.json()) as UserTradeSetupResult
}

/** Soft-delete a USER overlay (T2c). */
export async function deleteUserChartObject(objectId: string): Promise<void> {
  const res = await fetch(
    `/api/engine/chart-objects/item/${encodeURIComponent(objectId)}`,
    { method: 'DELETE', credentials: 'include' },
  )
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { detail?: string } | null
    throw new Error(body?.detail ?? `Erreur ${res.status}`)
  }
}

/** Zones usable by PriceChart (visual parity with former StructureOverlay.zones).
 * Also includes FVG rectangles (T9d) as dual price-line bands. */
export function chartObjectZones(objects: ChartObject[]): Array<{
  side: 'support' | 'resistance'
  low: number
  high: number
  touch_count: number
  label: string
  faded?: boolean
}> {
  return objects
    .filter(
      (o) =>
        (o.type === 'zone' || o.type === 'rectangle') &&
        o.price_low != null &&
        o.price_high != null,
    )
    .map((o) => {
      const status = typeof o.origin?.status === 'string' ? o.origin.status : ''
      const faded = status === 'filled' || status === 'invalidated' || status === 'partial'
      const kind = o.origin?.kind === 'fvg' ? 'FVG' : o.side === 'support' ? 'S' : 'R'
      return {
        side: (o.side === 'resistance' ? 'resistance' : 'support') as 'support' | 'resistance',
        low: o.price_low as number,
        high: o.price_high as number,
        touch_count: Number(o.origin?.touch_count ?? 0),
        label: o.label ?? (o.origin?.kind === 'fvg' ? kind : ''),
        faded,
      }
    })
}

/** Horizontal / entry / stop / target → single price lines. */
export function chartObjectPriceLevels(objects: ChartObject[]): Array<{
  price: number
  label: string
  kind: 'horizontal_line' | 'entry' | 'stop' | 'target'
  side: string | null
  subtype: string | null
}> {
  const kinds = new Set(['horizontal_line', 'entry', 'stop', 'target'])
  return objects
    .filter((o) => kinds.has(o.type) && o.points.length === 1)
    .map((o) => ({
      price: o.points[0]!.price,
      label: o.label ?? o.type,
      kind: o.type as 'horizontal_line' | 'entry' | 'stop' | 'target',
      side: o.side,
      subtype: o.subtype,
    }))
}

/** Trendlines + rays usable by PriceChart. */
export function chartObjectTrendlines(objects: ChartObject[]): Array<{
  side: 'support' | 'resistance'
  start_time: number
  end_time: number
  start_price: number
  end_price: number
  ray: boolean
}> {
  return objects
    .filter((o) => (o.type === 'trend_line' || o.type === 'ray') && o.points.length === 2)
    .map((o) => ({
      side: (o.side === 'resistance' ? 'resistance' : 'support') as 'support' | 'resistance',
      start_time: o.points[0]!.time,
      end_time: o.points[1]!.time,
      start_price: o.points[0]!.price,
      end_price: o.points[1]!.price,
      ray: o.type === 'ray',
    }))
}

/** Breakout / entry-like markers + text annotations — one point each. */
export function chartObjectMarkers(objects: ChartObject[]): Array<{
  time: number
  price: number
  side: string | null
  label: string
  confirmed: boolean
  shape: 'circle' | 'arrowUp' | 'arrowDown' | 'square'
  /** T4a: win|loss|flat for BACKTEST exit markers (null otherwise). */
  outcome: 'win' | 'loss' | 'flat' | null
}> {
  return objects
    .filter(
      (o) =>
        (o.type === 'marker' || o.type === 'text' || o.type === 'entry') &&
        o.points.length === 1,
    )
    .map((o) => {
      let shape: 'circle' | 'arrowUp' | 'arrowDown' | 'square' = 'circle'
      if (o.type === 'entry') {
        shape = o.side === 'SHORT' ? 'arrowDown' : 'arrowUp'
      } else if (o.type === 'text') {
        shape = 'square'
      }
      const rawOutcome = o.origin?.outcome
      const outcome =
        o.source === 'backtest' &&
        (rawOutcome === 'win' || rawOutcome === 'loss' || rawOutcome === 'flat')
          ? rawOutcome
          : null
      return {
        time: o.points[0]!.time,
        price: o.points[0]!.price,
        side: o.side,
        label: o.label ?? (o.type === 'entry' ? 'IN' : 'BO'),
        confirmed: Boolean(o.origin?.confirmed ?? true),
        shape,
        outcome,
      }
    })
}
