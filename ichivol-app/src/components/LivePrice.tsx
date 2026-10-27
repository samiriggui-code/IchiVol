import { displayPrice, formatLiveAge, isLiveCryptoSymbol, liveState } from '../lib/livePrices.ts'
import { useLiveFeedSummary, useLivePrice } from '../lib/useLivePrice.ts'
import './LivePrice.css'

/**
 * Prix courant d'une paire : en direct (flux public Binance) pour la crypto, sinon le prix du serveur.
 * Indicateur discret « direct » / « différé » avec l'âge du dernier prix. Affichage seulement.
 */
export function LivePrice({
  symbol,
  fallback,
  format,
}: {
  symbol: string | null | undefined
  fallback: number | null | undefined
  format: (n: number | null | undefined) => string
}) {
  const { tick, now } = useLivePrice(symbol)
  if (!isLiveCryptoSymbol(symbol)) return <>{format(fallback)}</>
  const d = displayPrice(tick, fallback, now)
  const age = d.ageMs != null ? formatLiveAge(d.ageMs) : null
  const title =
    d.state === 'live'
      ? `En direct (Binance) · dernier prix il y a ${age}`
      : age != null
        ? `Différé : flux Binance muet depuis ${age}, prix du serveur affiché`
        : 'Différé : prix du serveur (flux Binance pas encore reçu)'
  return (
    <span className={`lp lp-${d.state}`} title={title}>
      {format(d.price)}
      <span className="lp-dot" aria-hidden="true" />
      <span className="lp-sr">{d.state === 'live' ? `en direct, ${age}` : 'différé'}</span>
    </span>
  )
}

/** Indicateur global « Prix crypto en direct · 1 s » / « différés », à placer au-dessus d'un tableau. */
export function LiveFeedBadge() {
  const { tick, now, active } = useLiveFeedSummary()
  if (!active) return null
  const state = liveState(tick, now)
  const age = tick ? formatLiveAge(now - tick.receivedMs) : null
  return (
    <span
      className={`lp lp-badge lp-${state}`}
      title="Prix crypto lus directement sur le flux public Binance (affichage). Les stops sont contrôlés par le moteur."
    >
      <span className="lp-dot" aria-hidden="true" />
      {state === 'live' ? `Crypto en direct · ${age}` : age ? `Crypto différée · ${age}` : 'Crypto différée'}
    </span>
  )
}
