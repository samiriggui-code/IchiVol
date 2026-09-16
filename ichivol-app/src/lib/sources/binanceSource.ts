import { fetchKlines, fetchTickers24h } from '../binance'
import type { MarketSource } from './types'

/**
 * Feed public Binance Market Data Only (`data-api.binance.vision`).
 * @see https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md
 * Pas de clé API, pas d’ordres, pas de User Data Stream — IchiVol ne trade PAS ici.
 */
export const binanceSource: MarketSource = {
  id: 'binance',
  label: 'Binance Vision (data)',
  hint: 'OHLCV public · pas de compte trading',
  fetchKlines,
  fetchTickers24h,
}
