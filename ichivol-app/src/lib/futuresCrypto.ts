/**
 * Portefeuille Futures & Crypto (YM, MGC, BTC) : client de la vue dédiée et calculs par marché.
 * Moteur : engine/app/api/futures_crypto.py et engine/app/paper/futures_crypto.py.
 */

export const FUTURES_CRYPTO_LABEL = 'Futures & Crypto — YM, MGC, BTC'

export type BtcMode = 'spot' | 'perpetual' | 'cme'

/** Dernier verdict que la boucle 1h a donné à ce portefeuille (portes du pipeline : ce sur quoi il agit). */
export interface FuturesCryptoSignal {
  decision: 'BUY' | 'SELL' | 'WATCH' | 'NO_TRADE' | string
  direction: string
  price: number | null
  timeframe: string
  bar_close: string | null
  seen_at: string
  stages: { id: string; status: string; summary: string | null }[]
  /** opened / closed quand ce verdict a ouvert ou fermé une position, sinon null. */
  action: 'opened' | 'closed' | null
}

export interface FuturesCryptoMarket {
  slot: 'YM' | 'MGC' | 'BTC' | string
  symbol: string
  mode?: BtcMode
  name: string
  venue: string
  contract: string
  contract_size: number
  contract_unit: string
  price_source: string
  price_note: string
  open: boolean
  closed_trades: number
  wins: number
  realized_pnl: number
  last_signal: FuturesCryptoSignal | null
  costs: { commission_bps: number; friction_bps: number; financing_bps_per_day_long: number }
}

export interface BtcModeOption {
  mode: BtcMode
  symbol: string
  name: string
  venue: string
  contract: string
  contract_unit: string
  price_source: string
  price_note: string
}

export interface FuturesCryptoView {
  code: string
  label: string
  btc_mode: BtcMode
  btc_modes: BtcModeOption[]
  btc_mode_locked: boolean
  markets: FuturesCryptoMarket[]
  other_open_symbols: string[]
  rules: {
    timeframe: string
    entry: string
    allow_short: boolean
    risk_pct: number
    max_open_risk_pct: number
    max_notional_pct: number
    max_open_positions: number
    daily_loss_limit_pct: number
  }
}

async function errorText(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown }
    if (typeof body.detail === 'string') return body.detail
  } catch {
    /* corps non JSON */
  }
  return `Erreur ${res.status}`
}

export async function getFuturesCryptoView(): Promise<FuturesCryptoView> {
  const res = await fetch('/api/engine/paper/futures-crypto', { credentials: 'include' })
  if (!res.ok) throw new Error(await errorText(res))
  return res.json() as Promise<FuturesCryptoView>
}

export async function setBtcMode(mode: BtcMode): Promise<FuturesCryptoView> {
  const res = await fetch('/api/engine/paper/futures-crypto/btc-mode', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode }),
  })
  if (!res.ok) throw new Error(btcModeErrorFr(await errorText(res)))
  return res.json() as Promise<FuturesCryptoView>
}

/** Message moteur → phrase française. */
export function btcModeErrorFr(detail: string): string {
  if (detail.startsWith('btc_position_open')) {
    return 'Une position BTC est ouverte : ferme-la d’abord, sinon elle changerait d’instrument en cours de route.'
  }
  if (detail.startsWith('unknown_btc_mode')) return 'Mode BTC inconnu.'
  return detail
}

/** Quantité paper exprimée en contrats de la bourse (fractionnaire : un vrai compte demande des contrats entiers). */
export function contractsFor(qty: number | null | undefined, contractSize: number): number | null {
  if (qty == null || !Number.isFinite(qty) || !(contractSize > 0)) return null
  return Math.abs(qty) / contractSize
}

export interface MarketPositionLike {
  symbol: string
  status: string
  qty?: number | null
  risk_amount?: number | null
  notional?: number | null
  market_value?: number | null
  current_price?: number | null
}

export interface MarketRisk {
  symbol: string
  riskAmount: number
  /** Part du capital risquée jusqu'au stop. */
  riskPctOfEquity: number | null
  /** Part du plafond global consommée par ce marché (0..1+). */
  shareOfCap: number | null
  exposure: number
  exposurePctOfEquity: number | null
}

/** Risque et exposition d'un marché, à partir des positions ouvertes de l'aperçu du portefeuille. */
export function marketRisk(
  symbol: string,
  positions: ReadonlyArray<MarketPositionLike>,
  equity: number | null | undefined,
  maxOpenRiskPct: number,
): MarketRisk {
  const open = positions.filter((p) => p.symbol === symbol && String(p.status).toUpperCase() === 'OPEN')
  const riskAmount = open.reduce((s, p) => s + Math.max(0, Number(p.risk_amount ?? 0)), 0)
  const exposure = open.reduce((s, p) => {
    const mv =
      p.market_value ??
      (p.current_price != null && p.qty != null ? p.current_price * Math.abs(p.qty) : p.notional ?? 0)
    return s + Math.abs(Number(mv ?? 0))
  }, 0)
  const eq = equity != null && equity > 0 ? equity : null
  return {
    symbol,
    riskAmount,
    riskPctOfEquity: eq ? riskAmount / eq : null,
    shareOfCap: eq && maxOpenRiskPct > 0 ? riskAmount / (eq * maxOpenRiskPct) : null,
    exposure,
    exposurePctOfEquity: eq ? exposure / eq : null,
  }
}

/** Combien de positions de taille pleine peuvent encore s'ouvrir sous le plafond global. */
export function fullPositionsLeft(
  openRiskAmount: number,
  equity: number | null | undefined,
  riskPct: number,
  maxOpenRiskPct: number,
): number | null {
  if (equity == null || !(equity > 0) || !(riskPct > 0)) return null
  const room = equity * maxOpenRiskPct - Math.max(0, openRiskAmount)
  return Math.max(0, Math.floor(room / (equity * riskPct) + 1e-9))
}

const VERDICT_FR: Record<string, string> = {
  BUY: 'Achat',
  SELL: 'Vente',
  WATCH: 'À surveiller',
  NO_TRADE: 'Pas de trade',
}

export function verdictLabelFr(decision: string | null | undefined): string {
  return (decision && VERDICT_FR[decision]) || decision || '—'
}

/** Ce que le dernier verdict veut dire pour ce portefeuille, en une ou deux phrases. */
export function signalSentenceFr(signal: FuturesCryptoSignal | null, allowShort: boolean): string {
  if (!signal) {
    return 'Pas encore de lecture depuis le dernier démarrage du moteur : elle arrive au prochain passage de la boucle (toutes les 5 minutes).'
  }
  let base: string
  switch (signal.decision) {
    case 'BUY':
      base = 'Le signal IchiVol est haussier et toutes les portes sont passées.'
      break
    case 'SELL':
      base = allowShort
        ? 'Le signal IchiVol est baissier et toutes les portes sont passées.'
        : 'Le signal IchiVol est baissier. Ce portefeuille ne vend pas à découvert : il n’ouvre rien, il ferme seulement un achat en cours si la tendance s’inverse.'
      break
    case 'WATCH':
      base = 'Une tendance se dessine mais il manque des confirmations pour entrer.'
      break
    case 'NO_TRADE':
      base = 'Les conditions d’entrée ne sont pas réunies.'
      break
    default:
      base = `Verdict ${signal.decision}.`
  }
  if (signal.action === 'opened') return `${base} Une position a été ouverte sur ce signal.`
  if (signal.action === 'closed') return `${base} La position a été fermée à ce passage.`
  return base
}
