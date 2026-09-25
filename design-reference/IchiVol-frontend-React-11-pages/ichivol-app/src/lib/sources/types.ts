import type { Candle, Interval } from '../types'

export interface Ticker24h {
  symbol: string
  lastPrice: number
  priceChangePercent: number
  quoteVolume: number
}

export type ExchangeId = 'binance' | 'bybit' | 'okx'

export interface MarketSource {
  id: ExchangeId
  /** Libellé UI — toujours un *feed* de données, jamais un compte de trading. */
  label: string
  /** Une ligne d’aide sous le select (optionnel). */
  hint?: string
  fetchKlines(symbol: string, interval: Interval, limit?: number): Promise<Candle[]>
  fetchTickers24h(): Promise<Ticker24h[]>
}
