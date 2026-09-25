/** Client IndicatorRegistry — le chart ne calcule plus Ichimoku/RVOL localement. */

import type { Candle, IchimokuParams, IchimokuPoint, VolumeParams } from './types'

export interface EngineIchimokuState {
  time: number
  tenkan: number | null
  kijun: number | null
  senkou_a: number | null
  senkou_b: number | null
  cloud_top: number | null
  cloud_bot: number | null
  price_vs_kumo: string
}

export interface EngineRvolState {
  time: number
  volume: number
  avg_volume: number | null
  rvol: number | null
  confirmed: boolean
  spike: boolean
}

export interface ProjectedKumoPoint {
  time: number
  senkouA: number
  senkouB: number
}

async function parseError(res: Response): Promise<string> {
  const body = (await res.json().catch(() => null)) as
    | { detail?: string | unknown; message?: string }
    | null
  const detail = body?.detail
  if (typeof detail === 'string') return detail
  return body?.message ?? `Erreur ${res.status}`
}

/** Front IchimokuParams → engine snake_case. */
export function ichimokuParamsForEngine(p: IchimokuParams): Record<string, number> {
  return {
    tenkan: p.tenkan,
    kijun: p.kijun,
    senkou_b: p.senkouB,
    displacement: p.displacement,
  }
}

/** Front VolumeParams → engine RvolParams (seuils utiles au chart). */
export function rvolParamsForEngine(p: VolumeParams): Record<string, number> {
  return {
    primary_window: p.rvolLen,
    significant_threshold: p.rvolSignificant,
    strong_threshold: p.rvolStrong,
    anomaly_threshold: p.rvolAnomaly,
    low_threshold: p.rvolLow,
  }
}

export async function getIndicatorSeries<T = Record<string, unknown>>(
  id: string,
  symbol: string,
  timeframe: string,
  limit = 300,
  params?: Record<string, unknown>,
): Promise<{ series: T[]; params: Record<string, unknown>; warmup: number }> {
  const q = new URLSearchParams({ timeframe, limit: String(limit) })
  if (params && Object.keys(params).length > 0) {
    q.set('params', JSON.stringify(params))
  }
  const res = await fetch(
    `/api/engine/indicators/${encodeURIComponent(id)}/${encodeURIComponent(symbol)}?${q}`,
    { credentials: 'include' },
  )
  if (!res.ok) throw new Error(await parseError(res))
  const body = (await res.json()) as {
    series: T[]
    params: Record<string, unknown>
    warmup: number
  }
  return body
}

export async function getIchimokuProjection(
  symbol: string,
  timeframe: string,
  limit = 300,
  params?: IchimokuParams,
): Promise<ProjectedKumoPoint[]> {
  const q = new URLSearchParams({ timeframe, limit: String(limit) })
  if (params) q.set('params', JSON.stringify(ichimokuParamsForEngine(params)))
  const res = await fetch(
    `/api/engine/indicators/ichimoku/${encodeURIComponent(symbol)}/projection?${q}`,
    { credentials: 'include' },
  )
  if (!res.ok) throw new Error(await parseError(res))
  const body = (await res.json()) as {
    projection: Array<{ time_projected: number; senkou_a: number; senkou_b: number }>
  }
  return body.projection.map((p) => ({
    time: p.time_projected,
    senkouA: p.senkou_a,
    senkouB: p.senkou_b,
  }))
}

/**
 * Mappe les states moteur → IchimokuPoint (types chart existants).
 * Chikou = close décalé de `displacement` vers l'arrière (affichage seul).
 */
export function mapEngineIchimokuToPoints(
  states: EngineIchimokuState[],
  candles: Candle[],
  displacement: number,
): IchimokuPoint[] {
  const timeIndex = new Map(candles.map((c, i) => [c.time, i]))

  return states.map((s) => {
    const idx = timeIndex.get(s.time)
    let chikou: number | null = null
    if (idx != null) {
      const src = idx + displacement
      if (src < candles.length) chikou = candles[src].close
    }
    const pvk = s.price_vs_kumo
    return {
      time: s.time,
      tenkan: s.tenkan,
      kijun: s.kijun,
      senkouA: s.senkou_a,
      senkouB: s.senkou_b,
      chikou,
      cloudTop: s.cloud_top,
      cloudBot: s.cloud_bot,
      aboveCloud: pvk === 'ABOVE',
      belowCloud: pvk === 'BELOW',
      cloudBullish:
        s.senkou_a != null && s.senkou_b != null ? s.senkou_a >= s.senkou_b : false,
    }
  })
}

export async function fetchChartOverlays(
  symbol: string,
  timeframe: string,
  candles: Candle[],
  ichiParams: IchimokuParams,
  volParams: VolumeParams,
): Promise<{
  ichi: IchimokuPoint[]
  rvol: EngineRvolState[]
  projection: ProjectedKumoPoint[]
}> {
  const limit = Math.max(candles.length, 50)
  const [ichiRes, rvolRes, projection] = await Promise.all([
    getIndicatorSeries<EngineIchimokuState>(
      'ichimoku',
      symbol,
      timeframe,
      limit,
      ichimokuParamsForEngine(ichiParams),
    ),
    getIndicatorSeries<EngineRvolState>(
      'rvol',
      symbol,
      timeframe,
      limit,
      rvolParamsForEngine(volParams),
    ),
    getIchimokuProjection(symbol, timeframe, limit, ichiParams),
  ])

  // Align on candle times when lengths differ (warmup trim).
  const candleTimes = new Set(candles.map((c) => c.time))
  const ichiStates = ichiRes.series.filter((s) => candleTimes.has(s.time))
  const rvolStates = rvolRes.series.filter((s) => candleTimes.has(s.time))

  return {
    ichi: mapEngineIchimokuToPoints(ichiStates, candles, ichiParams.displacement),
    rvol: rvolStates,
    projection,
  }
}
