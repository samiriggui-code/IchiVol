import { useEffect, useState, useSyncExternalStore } from 'react'
import { LivePriceFeed, isLiveCryptoSymbol, type LiveTick } from './livePrices.ts'

/** Connexion unique du navigateur, partagée par toutes les cellules de prix. */
let shared: LivePriceFeed | null = null
function feed(): LivePriceFeed | null {
  if (typeof window === 'undefined' || typeof WebSocket === 'undefined') return null
  shared ??= new LivePriceFeed()
  return shared
}

const noopSubscribe = () => () => {}

/**
 * Dernier tick Binance d'une paire crypto (undefined hors crypto ou avant le premier message) et l'heure
 * courante, rafraîchie chaque seconde pour l'âge affiché.
 */
export function useLivePrice(symbol: string | null | undefined): { tick: LiveTick | undefined; now: number } {
  const f = isLiveCryptoSymbol(symbol) ? feed() : null
  useEffect(() => {
    if (!f || !symbol) return
    return f.acquire(symbol)
  }, [f, symbol])
  const tick = useSyncExternalStore(
    f ? (cb) => f.subscribe(cb) : noopSubscribe,
    () => (f && symbol ? f.get(symbol) : undefined),
    () => undefined,
  )
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!f) return
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [f])
  return { tick, now }
}

/** État global du flux du navigateur (paire la plus fraîche) : null tant qu'aucune paire crypto n'est affichée. */
export function useLiveFeedSummary(): { tick: LiveTick | undefined; now: number; active: boolean } {
  const f = feed()
  const tick = useSyncExternalStore(
    f ? (cb) => f.subscribe(cb) : noopSubscribe,
    () => f?.freshest(),
    () => undefined,
  )
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])
  return { tick, now, active: f != null && f.symbols().length > 0 }
}
