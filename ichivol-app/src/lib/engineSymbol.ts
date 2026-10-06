/** Instruments non crypto du catalogue moteur (engine/app/universe/catalog.py) : jamais suffixés USDT. */
export const NON_CRYPTO_ENGINE_SYMBOLS: ReadonlySet<string> = new Set([
  'EURUSD', 'GBPUSD', 'USDJPY', 'XAUUSD', 'XAGUSD', 'SPX', 'NDX', 'AAPL', 'TSLA', 'WTI',
])

/** Symbole attendu par le moteur : « BTC » → « BTCUSDT », mais « NDX » reste « NDX » (sinon NDXUSDT chez Binance). */
export function toEngineSymbol(raw: string): string {
  const s = raw.trim().toUpperCase()
  if (!s || s.endsWith('USDT') || NON_CRYPTO_ENGINE_SYMBOLS.has(s)) return s
  return `${s}USDT`
}
