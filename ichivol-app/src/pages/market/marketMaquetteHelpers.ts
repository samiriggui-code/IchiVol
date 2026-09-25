/** Marché — helpers d’affichage (maquette). Pas de composants. */

import type { DecisionPipelineView, PipelineStageStatus } from '../../lib/decisionPipeline'
import { displaySymbol } from '../../lib/markets'

export type MaquetteBadgeTone = 'green' | 'amber' | 'red' | 'gray' | ''

/** Libellés maquette PASSE / PRUDENCE / ÉCHEC. */
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
    default: {
      const _exhaustive: never = status
      return _exhaustive
    }
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
  const lookback = Math.min(24, candles.length - 1)
  const prev = candles[candles.length - 1 - lookback]!.close
  if (!prev) return null
  return ((last - prev) / prev) * 100
}

/**
 * Phrase FR lisible pour « Lecture du marché » — pas de score/conf/delta brut.
 * Ex. « Structure baissière. Le prix évolue sous le nuage ; participation insuffisante (RVOL 0,99×). »
 */
export function lectureSynthesisFr(
  pipeline: DecisionPipelineView | null,
  rvol: number | null | undefined,
): string {
  if (!pipeline) return '—'

  const dir =
    pipeline.direction === 'LONG'
      ? 'haussière'
      : pipeline.direction === 'SHORT'
        ? 'baissière'
        : 'neutre'

  const byId = new Map(pipeline.stages.map((s) => [s.id, s]))
  const structure = byId.get('structure')
  const participation = byId.get('participation')
  const location = byId.get('location')
  const direction = byId.get('direction')

  let cloudClause = 'le contexte structurel reste à préciser'
  if (direction?.status === 'pass' && pipeline.direction === 'LONG') {
    cloudClause = 'le prix évolue au-dessus du nuage'
  } else if (direction?.status === 'pass' && pipeline.direction === 'SHORT') {
    cloudClause = 'le prix évolue sous le nuage'
  } else if (location?.status === 'pass') {
    cloudClause = 'l’emplacement est favorable'
  } else if (location?.status === 'fail') {
    cloudClause = 'l’emplacement n’est pas favorable'
  } else if (structure?.status === 'watch' || structure?.status === 'fail') {
    cloudClause = 'la structure demande confirmation'
  }

  const rvolTxt = fmtRvolMaq(rvol)
  let partClause = 'participation à confirmer'
  if (participation?.status === 'pass') {
    partClause = rvol != null ? `participation confirmée (RVOL ${rvolTxt})` : 'participation confirmée'
  } else if (participation?.status === 'watch' || participation?.status === 'fail') {
    partClause =
      rvol != null ? `participation insuffisante (RVOL ${rvolTxt})` : 'participation insuffisante'
  }

  const structLead =
    structure?.status === 'pass'
      ? `Structure ${dir}`
      : structure?.status === 'fail'
        ? `Structure ${dir} non validée`
        : `Structure ${dir}`

  return `${structLead}. ${cloudClause.charAt(0).toUpperCase()}${cloudClause.slice(1)} ; ${partClause}.`
}
