export interface GlobalMarketData {
  totalMarketCapUsd: number
  totalVolumeUsd: number
  marketCapChangePercent24h: number
  dominance: { symbol: string; percent: number }[]
}

export interface FearGreed {
  value: number
  classification: string
  timestamp: number
}

export interface MarketCoin {
  id: string
  symbol: string
  name: string
  rank: number
  priceUsd: number
  marketCapUsd: number
  volume24hUsd: number
  changePercent24h: number | null
}

/** CoinGecko free : ~5–10 req/min — TTL long + dédup + cooldown échec. */
const COINGECKO_TTL_MS = 5 * 60_000
/** Après 502/429/réseau : ne pas re-frapper à chaque HMR / remount. */
const FAIL_COOLDOWN_MS = 2 * 60_000
const STORAGE_PREFIX = 'ichivol:mkt:'

type CacheEntry<T> = { value: T; expiresAt: number }
type FailEntry = { error: string; until: number }

const cache = new Map<string, CacheEntry<unknown>>()
const fails = new Map<string, FailEntry>()
const inflight = new Map<string, Promise<unknown>>()

function readPersisted<T>(key: string): CacheEntry<T> | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_PREFIX + key)
    if (!raw) return null
    const parsed = JSON.parse(raw) as CacheEntry<T>
    if (!parsed || typeof parsed.expiresAt !== 'number') return null
    return parsed
  } catch {
    return null
  }
}

function writePersisted<T>(key: string, entry: CacheEntry<T>): void {
  try {
    sessionStorage.setItem(STORAGE_PREFIX + key, JSON.stringify(entry))
  } catch {
    /* quota / private mode */
  }
}

async function cachedFetch<T>(key: string, ttlMs: number, loader: () => Promise<T>): Promise<T> {
  const mem = cache.get(key) as CacheEntry<T> | undefined
  if (mem && mem.expiresAt > Date.now()) return mem.value

  const persisted = readPersisted<T>(key)
  if (persisted) {
    cache.set(key, persisted)
    if (persisted.expiresAt > Date.now()) return persisted.value
  }

  const fail = fails.get(key)
  if (fail && fail.until > Date.now()) {
    if (persisted) return persisted.value
    if (mem) return mem.value
    throw new Error(fail.error)
  }

  const pending = inflight.get(key) as Promise<T> | undefined
  if (pending) return pending

  const stale = mem ?? persisted ?? undefined

  const promise = loader()
    .then((value) => {
      const entry = { value, expiresAt: Date.now() + ttlMs }
      cache.set(key, entry)
      writePersisted(key, entry)
      fails.delete(key)
      return value
    })
    .catch((err: unknown) => {
      const message = err instanceof Error ? err.message : 'Erreur marché'
      fails.set(key, { error: message, until: Date.now() + FAIL_COOLDOWN_MS })
      if (stale) return stale.value
      throw err
    })
    .finally(() => {
      inflight.delete(key)
    })

  inflight.set(key, promise)
  return promise
}

interface CoinGeckoGlobalResponse {
  data: {
    total_market_cap: Record<string, number>
    total_volume: Record<string, number>
    market_cap_percentage: Record<string, number>
    market_cap_change_percentage_24h_usd: number
  }
}

export async function fetchGlobalMarket(): Promise<GlobalMarketData> {
  return cachedFetch('coingecko:global', COINGECKO_TTL_MS, async () => {
    const res = await fetch('/coingecko/api/v3/global')
    if (res.status === 429) {
      throw new Error('CoinGecko rate limit — réessaie dans 2 min')
    }
    if (!res.ok) throw new Error(`CoinGecko indisponible (${res.status})`)
    const body = (await res.json()) as CoinGeckoGlobalResponse
    const dominance = Object.entries(body.data.market_cap_percentage)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([symbol, percent]) => ({ symbol: symbol.toUpperCase(), percent }))
    return {
      totalMarketCapUsd: body.data.total_market_cap.usd,
      totalVolumeUsd: body.data.total_volume.usd,
      marketCapChangePercent24h: body.data.market_cap_change_percentage_24h_usd,
      dominance,
    }
  })
}

interface FearGreedResponse {
  data: { value: string; value_classification: string; timestamp: string }[]
}

export async function fetchFearGreed(): Promise<FearGreed> {
  return cachedFetch('feargreed:1', COINGECKO_TTL_MS, async () => {
    const res = await fetch('/feargreed/fng/?limit=1')
    if (!res.ok) throw new Error(`Fear & Greed ${res.status}`)
    const body = (await res.json()) as FearGreedResponse
    const point = body.data[0]
    return {
      value: Number(point.value),
      classification: point.value_classification,
      timestamp: Number(point.timestamp) * 1000,
    }
  })
}

/** Historique court Fear & Greed (page Contexte approfondie). */
export async function fetchFearGreedHistory(limit = 7): Promise<FearGreed[]> {
  return cachedFetch(`feargreed:${limit}`, COINGECKO_TTL_MS, async () => {
    const res = await fetch(`/feargreed/fng/?limit=${limit}`)
    if (!res.ok) throw new Error(`Fear & Greed ${res.status}`)
    const body = (await res.json()) as FearGreedResponse
    return body.data.map((point) => ({
      value: Number(point.value),
      classification: point.value_classification,
      timestamp: Number(point.timestamp) * 1000,
    }))
  })
}

interface CoinGeckoMarketRow {
  id: string
  symbol: string
  name: string
  market_cap_rank: number | null
  current_price: number
  market_cap: number
  total_volume: number
  price_change_percentage_24h: number | null
}

/** Top coins par market cap — détail page Contexte (pas le screener IchiVol). */
export async function fetchTopMarkets(limit = 20): Promise<MarketCoin[]> {
  return cachedFetch(`coingecko:markets:${limit}`, COINGECKO_TTL_MS, async () => {
    const params = new URLSearchParams({
      vs_currency: 'usd',
      order: 'market_cap_desc',
      per_page: String(limit),
      page: '1',
      sparkline: 'false',
      price_change_percentage: '24h',
    })
    const res = await fetch(`/coingecko/api/v3/coins/markets?${params}`)
    if (res.status === 429) {
      throw new Error('CoinGecko rate limit — réessaie dans 2 min')
    }
    if (!res.ok) throw new Error(`CoinGecko markets indisponible (${res.status})`)
    const body = (await res.json()) as CoinGeckoMarketRow[]
    return body.map((c) => ({
      id: c.id,
      symbol: c.symbol.toUpperCase(),
      name: c.name,
      rank: c.market_cap_rank ?? 0,
      priceUsd: c.current_price,
      marketCapUsd: c.market_cap,
      volume24hUsd: c.total_volume,
      changePercent24h: c.price_change_percentage_24h,
    }))
  })
}
