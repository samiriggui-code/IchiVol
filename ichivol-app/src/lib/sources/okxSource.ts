import type { Candle, Interval } from '../types'
import type { MarketSource, Ticker24h } from './types'

const PROXY = '/okx'

const INTERVAL_MAP: Record<Interval, string> = {
  '15m': '15m',
  '1h': '1H',
  '4h': '4H',
  '1d': '1D',
}

interface OkxResponse<T> {
  code: string
  msg: string
  data: T
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${PROXY}${path}`)
  if (!res.ok) throw new Error(`OKX ${res.status}: ${path}`)
  const body = (await res.json()) as OkxResponse<T>
  if (body.code !== '0') throw new Error(`OKX API: ${body.msg}`)
  return body.data
}

// OKX uses dash-separated instIds ("BTC-USDT"); the rest of the app uses
// concatenated symbols ("BTCUSDT") to stay consistent across exchanges.
function toInstId(symbol: string): string {
  if (!symbol.endsWith('USDT')) throw new Error(`Unsupported symbol for OKX: ${symbol}`)
  return `${symbol.slice(0, -4)}-USDT`
}

function fromInstId(instId: string): string {
  return instId.replace('-', '')
}

type OkxCandle = [string, string, string, string, string, string, string, string, string]

async function fetchKlines(symbol: string, interval: Interval, limit = 300): Promise<Candle[]> {
  const q = new URLSearchParams({
    instId: toInstId(symbol),
    bar: INTERVAL_MAP[interval],
    limit: String(Math.min(limit, 300)),
  })
  const data = await getJson<OkxCandle[]>(`/api/v5/market/candles?${q}`)
  // OKX returns candles newest-first.
  return data
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

interface OkxTicker {
  instId: string
  last: string
  open24h: string
  volCcy24h: string
}

async function fetchTickers24h(): Promise<Ticker24h[]> {
  const data = await getJson<OkxTicker[]>('/api/v5/market/tickers?instType=SPOT')
  return data
    .filter((t) => t.instId.endsWith('-USDT'))
    .map((t) => {
      const last = Number(t.last)
      const open24h = Number(t.open24h)
      return {
        symbol: fromInstId(t.instId),
        lastPrice: last,
        priceChangePercent: open24h ? ((last - open24h) / open24h) * 100 : 0,
        quoteVolume: Number(t.volCcy24h),
      }
    })
}

export const okxSource: MarketSource = {
  id: 'okx',
  label: 'OKX (data)',
  hint: 'OHLCV public · feed seulement',
  fetchKlines,
  fetchTickers24h,
}
