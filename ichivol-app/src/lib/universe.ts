/** Client pour GET /api/engine/universe + OHLCV moteur. */

export type EngineAssetClass = 'crypto' | 'forex' | 'index' | 'equity' | 'metal' | 'energy'

export interface EngineInstrument {
  id: string
  asset_class: EngineAssetClass
  label: string
  provider: string | null
  provider_symbol: string | null
  wired: boolean
  enabled: boolean
  quote: string
}

export interface EngineUniverse {
  classes: EngineAssetClass[]
  instruments: EngineInstrument[]
}

export interface EngineCandle {
  time: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}

async function parseError(res: Response): Promise<string> {
  const body = (await res.json().catch(() => null)) as
    | { detail?: string; message?: string; error?: string }
    | null
  return body?.detail ?? body?.message ?? body?.error ?? `Erreur ${res.status}`
}

export async function getEngineUniverse(): Promise<EngineUniverse> {
  const res = await fetch('/api/engine/universe', { credentials: 'include' })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<EngineUniverse>
}

export async function getEngineOhlcv(
  symbol: string,
  timeframe: string,
  limit = 300,
): Promise<{ symbol: string; timeframe: string; provider: string; candles: EngineCandle[] }> {
  const q = new URLSearchParams({ timeframe, limit: String(limit) })
  const res = await fetch(`/api/engine/ohlcv/${encodeURIComponent(symbol)}?${q}`, {
    credentials: 'include',
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<{
    symbol: string
    timeframe: string
    provider: string
    candles: EngineCandle[]
  }>
}

export const CLASS_LABELS: Record<EngineAssetClass, string> = {
  crypto: 'Crypto',
  forex: 'Forex',
  metal: 'Métaux',
  index: 'Indices',
  equity: 'Actions',
  energy: 'Énergie',
}

export const CLASS_BLURBS: Record<EngineAssetClass, string> = {
  crypto: 'Spot crypto via Binance Vision (données publiques, pas un compte broker).',
  forex: 'Devises via Twelve Data — volume souvent tick / limité pour le RVOL.',
  metal: 'Métaux (XAU/XAG) via Twelve Data — pas le marché LME physique.',
  index: 'Indices via Twelve Data.',
  equity: 'Actions cotées via Twelve Data (pas des tokens exchange).',
  energy: 'Énergie — provider à câbler.',
}
