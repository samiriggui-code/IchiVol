import type { Candle, Interval } from '../types'
import type { MarketSource, Ticker24h } from './types'

const PROXY = '/bybit'

const INTERVAL_MAP: Record<Interval, string> = {
  '15m': '15',
  '1h': '60',
  '4h': '240',
  '1d': 'D',
}

interface BybitResponse<T> {
  retCode: number
  retMsg: string
  result: T
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${PROXY}${path}`)
  if (!res.ok) throw new Error(`Bybit ${res.status}: ${path}`)
  const body = (await res.json()) as BybitResponse<T>
  if (body.retCode !== 0) throw new Error(`Bybit API: ${body.retMsg}`)
  return body.result
}

interface BybitKlineResult {
  list: [string, string, string, string, string, string, string][]
}

interface BybitTickerResult {
  list: { symbol: string; lastPrice: string; price24hPcnt: string; turnover24h: string }[]
}

async function fetchKlines(symbol: string, interval: Interval, limit = 300): Promise<Candle[]> {
  const q = new URLSearchParams({
    category: 'spot',
    symbol,
    interval: INTERVAL_MAP[interval],
    limit: String(Math.min(limit, 1000)),
  })
  const result = await getJson<BybitKlineResult>(`/v5/market/kline?${q}`)
  // Bybit returns candles newest-first.
  return result.list
    .map((k) => ({
      time: Math.floor(Number(k[0]) / 1000),
      open: Number(k[1]),
      high: Number(k[2]),
      low: Number(k[3]),
      close: Number(k[4]),
      volume: Number(k[5]),
    }))
    .sort((a, b) => a.time - b.time)
}

async function fetchTickers24h(): Promise<Ticker24h[]> {
  const result = await getJson<BybitTickerResult>('/v5/market/tickers?category=spot')
  return result.list
    .filter((t) => t.symbol.endsWith('USDT'))
    .map((t) => ({
      symbol: t.symbol,
      lastPrice: Number(t.lastPrice),
      priceChangePercent: Number(t.price24hPcnt) * 100,
      quoteVolume: Number(t.turnover24h),
    }))
}

export const bybitSource: MarketSource = {
  id: 'bybit',
  label: 'Bybit (data)',
  hint: 'OHLCV public · feed seulement',
  fetchKlines,
  fetchTickers24h,
}
