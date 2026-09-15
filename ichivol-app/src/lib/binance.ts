import type { Candle, Interval } from './types'

const PROXY = '/binance'

export const INTERVALS: { id: Interval; label: string }[] = [
  { id: '15m', label: '15m' },
  { id: '1h', label: '1H' },
  { id: '4h', label: '4H' },
  { id: '1d', label: '1D' },
]

export const WATCHLIST = [
  'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT',
  'ADAUSDT', 'DOGEUSDT', 'AVAXUSDT', 'LINKUSDT', 'DOTUSDT',
  'LTCUSDT', 'ATOMUSDT', 'UNIUSDT', 'NEARUSDT', 'APTUSDT',
  'ARBUSDT', 'OPUSDT', 'SUIUSDT', 'PEPEUSDT', 'TONUSDT',
] as const

type BinanceKline = [number, string, string, string, string, string, ...unknown[]]

export interface Ticker24h {
  symbol: string
  lastPrice: number
  priceChangePercent: number
  quoteVolume: number
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${PROXY}${path}`)
  if (!res.ok) throw new Error(`Market data ${res.status}: ${path}`)
  return res.json() as Promise<T>
}

export async function fetchKlines(
  symbol: string,
  interval: Interval,
  limit = 300,
): Promise<Candle[]> {
  const q = new URLSearchParams({ symbol, interval, limit: String(limit) })
  const raw = await getJson<BinanceKline[]>(`/api/v3/klines?${q}`)
  return raw.map((k) => ({
    time: Math.floor(Number(k[0]) / 1000),
    open: Number(k[1]),
    high: Number(k[2]),
    low: Number(k[3]),
    close: Number(k[4]),
    volume: Number(k[5]),
  }))
}

export async function fetchTickers24h(): Promise<Ticker24h[]> {
  const raw = await getJson<
    { symbol: string; lastPrice: string; priceChangePercent: string; quoteVolume: string }[]
  >('/api/v3/ticker/24hr')
  return raw
    .filter((t) => t.symbol.endsWith('USDT') && !t.symbol.includes('_'))
    .map((t) => ({
      symbol: t.symbol,
      lastPrice: Number(t.lastPrice),
      priceChangePercent: Number(t.priceChangePercent),
      quoteVolume: Number(t.quoteVolume),
    }))
}

export async function mapPool<T, R>(
  items: readonly T[],
  concurrency: number,
  fn: (item: T) => Promise<R>,
): Promise<R[]> {
  const results: R[] = new Array(items.length)
  let cursor = 0
  async function worker() {
    while (cursor < items.length) {
      const i = cursor++
      results[i] = await fn(items[i])
    }
  }
  await Promise.all(
    Array.from({ length: Math.min(concurrency, items.length) }, () => worker()),
  )
  return results
}
