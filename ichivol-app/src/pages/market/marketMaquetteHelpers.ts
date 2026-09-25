/** Marché — helpers d’affichage (maquette). Pas de composants. */

import type { DecisionPipelineView, PipelineStageStatus } from '../../lib/decisionPipeline'
import type { ChartObject } from '../../lib/chartObjects'
import { layerFromSource } from '../../lib/marketPrefs'
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

/** Niveau S/R : « 67 850 », « 2 645,3 », « 0,5862 » (même règle que l'axe du graphique). */
function fmtLevelMaq(n: number): string {
  const a = Math.abs(n)
  const digits = a >= 10_000 ? 0 : a >= 100 ? 1 : a >= 1 ? 2 : 4
  return n.toLocaleString('fr-FR', { maximumFractionDigits: digits })
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

/**
 * Maquette : une seule résistance (au-dessus du prix) et un seul support (en dessous),
 * les plus proches, tirés des objets STRUCTURE du moteur (zones + lignes horizontales).
 * Renvoie 0 à 2 objets « horizontal_line » (subtype sr_nearest) prêts pour PriceChart.
 */
export function nearestSrObjects(
  objects: ChartObject[],
  price: number | null | undefined,
  symbol: string,
  timeframe: string,
): ChartObject[] {
  if (price == null || !Number.isFinite(price) || price <= 0) return []
  let res: number | null = null
  let sup: number | null = null
  for (const o of objects) {
    if (layerFromSource(o.source, o.layer) !== 'structure') continue
    const levels: number[] = []
    if ((o.type === 'zone' || o.type === 'rectangle') && o.price_low != null && o.price_high != null) {
      if (o.origin?.kind === 'fvg') continue
      const st = typeof o.origin?.status === 'string' ? o.origin.status : ''
      if (st === 'invalidated') continue
      levels.push(o.price_low, o.price_high)
    } else if (o.type === 'horizontal_line' && o.points.length === 1) {
      levels.push(o.points[0]!.price)
    } else {
      continue
    }
    for (const lv of levels) {
      if (!Number.isFinite(lv)) continue
      if (lv > price && (res == null || lv < res)) res = lv
      if (lv < price && (sup == null || lv > sup)) sup = lv
    }
  }
  const mk = (id: string, lv: number, side: 'resistance' | 'support', label: string): ChartObject => ({
    id,
    type: 'horizontal_line',
    source: 'engine',
    layer: 'structure',
    symbol,
    timeframe,
    points: [{ time: 0, price: lv }],
    price_low: null,
    price_high: null,
    side,
    label: `${label} · ${fmtLevelMaq(lv)}`,
    confidence: 1,
    as_of: 0,
    origin: {},
    subtype: 'sr_nearest',
  })
  const out: ChartObject[] = []
  if (res != null) out.push(mk('sr-nearest-r', res, 'resistance', 'RÉSISTANCE'))
  if (sup != null) out.push(mk('sr-nearest-s', sup, 'support', 'SUPPORT'))
  return out
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
