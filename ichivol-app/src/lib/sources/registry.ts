import { binanceSource } from './binanceSource'
import { bybitSource } from './bybitSource'
import { okxSource } from './okxSource'
import type { ExchangeId, MarketSource } from './types'

export const SOURCES: Record<ExchangeId, MarketSource> = {
  binance: binanceSource,
  bybit: bybitSource,
  okx: okxSource,
}

export const SOURCE_LIST: MarketSource[] = Object.values(SOURCES)

export const DEFAULT_SOURCE_ID: ExchangeId = 'binance'

export type { ExchangeId, MarketSource }
