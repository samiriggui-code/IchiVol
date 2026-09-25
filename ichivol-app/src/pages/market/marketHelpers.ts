import { labelDecision, labelPipelineGate } from '../../lib/decisionLabels'
import type { ScreenerDecisionRow } from '../../lib/decisions'
import type { UserDecisionRow } from '../../lib/userDecisions'
import type { EngineAssetClass } from '../../lib/universe'
import type { Candle, Interval, ScreenerRow } from '../../lib/types'
import type { UserTradePointType } from '../../lib/chartObjects'
import type { IndicatorLayerKey } from '../../lib/marketPrefs'

export const ENGINE_TIMEFRAMES = new Set<Interval>(['15m', '1h', '4h', '1d'])
export const MARK_STEPS: UserTradePointType[] = ['entry', 'stop', 'target']

export const INDICATOR_TOGGLES: { key: IndicatorLayerKey; label: string }[] = [
  { key: 'candles', label: 'Bougies' },
  { key: 'tenkan', label: 'Tenkan' },
  { key: 'kijun', label: 'Kijun' },
  { key: 'spanA', label: 'Span A' },
  { key: 'spanB', label: 'Span B' },
  { key: 'volume', label: 'Volume' },
  { key: 'signals', label: 'Signaux' },
]

export function newSetupId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `setup-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}

export function decisionToBias(d: ScreenerDecisionRow['decision']): ScreenerRow['bias'] {
  if (d === 'STRONG_BUY' || d === 'BUY') return 'bull'
  if (d === 'STRONG_SELL' || d === 'SELL') return 'bear'
  return 'neutral'
}

export function friendlyDataError(raw: string): string {
  const lower = raw.toLowerCase()
  if (lower.includes('timeout') || lower.includes('aborted') || lower.includes('dépassé')) {
    return (
      'Timeout moteur (screener trop long). Avec des seuils Settings custom le cache est bypassé. ' +
      'Remets les défauts RVOL/ATR ou attends le scan live.'
    )
  }
  if (lower.includes('credit') || lower.includes('rate limit') || lower.includes('8 api')) {
    return (
      'Quota Twelve Data (≈8 crédits/min) dépassé. Attends ~1 minute. ' +
      'Sur Forex/Métaux/Actions : un seul instrument à la fois (pas de scan parallèle).'
    )
  }
  return raw
}

export function fmtPrice(n: number | null): string {
  if (n == null || !Number.isFinite(n)) return '—'
  return n.toLocaleString('fr-FR', { maximumFractionDigits: n >= 100 ? 2 : 6 })
}

export function fmtPct(n: number | null): string {
  if (n == null || !Number.isFinite(n)) return '—'
  const sign = n > 0 ? '+' : ''
  return `${sign}${n.toLocaleString('fr-FR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} %`
}

export function fmtRvol(n: number | null): string {
  if (n == null || !Number.isFinite(n)) return '—'
  return `${n.toLocaleString('fr-FR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}×`
}

/** Variation ≈24h depuis les bougies OHLCV (jamais inventée). */
export function change24hFromCandles(candles: Candle[]): number | null {
  if (candles.length < 2) return null
  const last = candles[candles.length - 1]
  if (!last || !Number.isFinite(last.close) || last.close === 0) return null
  const target = last.time - 24 * 3600
  let best = candles[0]
  let bestDist = Math.abs((best?.time ?? 0) - target)
  for (let i = 1; i < candles.length - 1; i++) {
    const c = candles[i]
    if (!c) continue
    const dist = Math.abs(c.time - target)
    if (dist < bestDist) {
      best = c
      bestDist = dist
    }
  }
  if (!best || !Number.isFinite(best.close) || best.close === 0) return null
  // Pas assez d’historique (~<12h) → Non disponible plutôt qu’un faux 24h.
  if (last.time - best.time < 12 * 3600) return null
  return ((last.close - best.close) / best.close) * 100
}

export function journalGateLabel(row: UserDecisionRow): string {
  if (row.gateDecision) {
    return labelPipelineGate(row.gateDecision as 'BUY' | 'SELL' | 'WATCH' | 'NO_TRADE')
  }
  if (row.signalKind) {
    return labelDecision(
      row.signalKind as
        | 'STRONG_BUY'
        | 'BUY'
        | 'WATCH'
        | 'WAIT'
        | 'SELL'
        | 'STRONG_SELL',
    )
  }
  return 'Non disponible'
}

export function isAssetClass(v: string | null): v is EngineAssetClass {
  return (
    v === 'crypto' ||
    v === 'forex' ||
    v === 'metal' ||
    v === 'index' ||
    v === 'equity' ||
    v === 'energy'
  )
}
