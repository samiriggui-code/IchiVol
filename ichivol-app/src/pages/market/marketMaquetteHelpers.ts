/** Marché — helpers d’affichage (maquette). Pas de composants. */

import type { PipelineStageStatus } from '../../lib/decisionPipeline'
import { displaySymbol } from '../../lib/markets'


export type MaquetteBadgeTone = 'green' | 'amber' | 'red' | 'gray' | ''

/** Libellés maquette PASSE / PRUDENCE / ÉCHEC (pas OK/Bloqué). */
export function maquetteGateBadge(
  status: PipelineStageStatus | null | undefined,
): { text: string; tone: MaquetteBadgeTone } {
  switch (status) {
    case 'pass':
      return { text: 'PASSE', tone: 'green' }
    case 'watch':
      return { text: 'PRUDENCE', tone: 'amber' }
    case 'fail':
      return { text: 'ÉCHEC', tone: 'red' }
    case 'pending':
    case 'skip':
    case null:
    case undefined:
      return { text: '—', tone: 'gray' }
    default:
      return { text: '—', tone: 'gray' }
  }
}

export function fmtPriceMaq(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n) || n === 0) return '—'
  return n.toLocaleString('fr-FR', {
    maximumFractionDigits: n >= 100 ? 2 : 6,
  })
}

export function fmtPctMaq(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return '—'
  const sign = n > 0 ? '+' : ''
  return `${sign}${n.toLocaleString('fr-FR', { maximumFractionDigits: 2, minimumFractionDigits: 2 })} %`
}

export function fmtRvolMaq(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return '—'
  return `${n.toLocaleString('fr-FR', { maximumFractionDigits: 2, minimumFractionDigits: 2 })}×`
}

export function shortSymbol(id: string): string {
  return displaySymbol(id)
}

export function change24hFromCandles(
  candles: { close: number }[],
): number | null {
  if (candles.length < 2) return null
  const last = candles[candles.length - 1]!.close
  // ~24h on 1h = 24 bars; fall back to first candle of series
  const lookback = Math.min(24, candles.length - 1)
  const prev = candles[candles.length - 1 - lookback]!.close
  if (!prev) return null
  return ((last - prev) / prev) * 100
}
