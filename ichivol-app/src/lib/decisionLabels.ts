import type { AgentDirection, DecisionDetail, DecisionLabel, PipelineGateLabel } from './decisions'

/** Libellés FR pour les codes machine du moteur (raisons / risques / invalidation). */
const REASON_FR: Record<string, string> = {
  // Ichimoku — bullish
  price_above_kumo: 'Prix au-dessus du nuage (kumo)',
  bullish_tk_cross: 'Croisement Tenkan/Kijun haussier',
  bullish_future_kumo: 'Nuage futur haussier (Senkou A > B)',
  chikou_confirmation: 'Chikou confirme (espace libre)',
  kumo_breakout_bullish: 'Cassure haussière du nuage',

  // Ichimoku — bearish
  price_below_kumo: 'Prix sous le nuage (kumo)',
  bearish_tk_cross: 'Croisement Tenkan/Kijun baissier',
  bearish_future_kumo: 'Nuage futur baissier (Senkou A < B)',
  kumo_breakout_bearish: 'Cassure baissière du nuage',

  // Ichimoku — neutre / data
  insufficient_confluence: 'Pas assez de confluence Ichimoku',
  insufficient_history: 'Historique insuffisant',

  // Invalidation
  close_back_inside_kumo: 'Clôture de retour dans le nuage',

  // RVOL
  volume_anomaly: 'Volume anormalement élevé (anomalie)',
  strong_relative_volume: 'Volume relatif très fort',
  significant_relative_volume: 'Volume relatif significatif',
  volume_accelerating: 'Volume en accélération',
  low_participation: 'Faible participation (volume faible)',
  normal_participation: 'Participation normale',
  high_relative_volume: 'Volume relatif élevé',

  // Risques combiner
  low_relative_volume_participation: 'Participation volume faible — signal peu confirmé',
  incomplete_ichimoku_confluence: 'Confluence Ichimoku incomplète',
  no_clear_structural_bias: 'Pas de biais structurel clair',

  // Structure / MTF (pipeline V1)
  structure_aligned: 'Structure prix alignée avec la direction',
  structure_opposed: 'Structure prix opposée à la direction',
  bos_confirms_direction: 'BOS confirme la direction',
  bos_invalidates_direction: 'BOS invalide la direction',
  mtf_aligned: 'Multi-timeframe aligné',
  mtf_opposed: 'Multi-timeframe opposé (contre-tendance)',

  // Régime ATR
  regime_dead: 'Régime de volatilité mort',
  regime_extreme: 'Volatilité extrême',
  regime_normal: 'Régime de volatilité normal',

  // Location V1.5 — Volume Profile / VWAP / AVWAP
  beyond_value_area: 'Prix hors de la value area',
  wrong_side_value_area: 'Mauvais côté de la value area',
  inside_value_area: 'Prix dans la value area',
  avwap_aligned: 'Aligné avec le VWAP ancré (AVWAP)',
  avwap_opposed: 'Contre le VWAP ancré (AVWAP)',
  above_vwap: 'Au-dessus du VWAP',
  below_vwap: 'Sous le VWAP',
  congestion_hvn: 'Congestion (HVN — zone de volume dense)',
  thin_liquidity_lvn: 'Liquidité fine (LVN)',
}

const DECISION_FR: Record<DecisionLabel, string> = {
  STRONG_BUY: 'Achat fort',
  BUY: 'Achat',
  WATCH: 'À surveiller',
  WAIT: 'Attendre',
  SELL: 'Vente',
  STRONG_SELL: 'Vente forte',
}

const PIPELINE_GATE_FR: Record<PipelineGateLabel, string> = {
  BUY: 'Achat (portes)',
  SELL: 'Vente (portes)',
  WATCH: 'Surveillance (portes)',
  NO_TRADE: 'Pas de trade',
}

const DIRECTION_FR: Record<AgentDirection, string> = {
  LONG: 'Hausse',
  SHORT: 'Baisse',
  NEUTRAL: 'Neutre',
}

export function labelReason(code: string): string {
  return REASON_FR[code] ?? code.replace(/_/g, ' ')
}

export function labelDecision(code: DecisionLabel): string {
  return DECISION_FR[code] ?? code
}

export function labelPipelineGate(code: PipelineGateLabel): string {
  return PIPELINE_GATE_FR[code] ?? code
}

export function labelDirection(code: AgentDirection): string {
  return DIRECTION_FR[code] ?? code
}

function confPhrase(pct: number): string {
  if (pct >= 90) return 'très élevée'
  if (pct >= 70) return 'élevée'
  if (pct >= 50) return 'moyenne'
  if (pct >= 30) return 'faible'
  return 'très faible'
}

function rvolPhrase(rvol: number | null): string {
  if (rvol == null) return 'volume relatif indisponible'
  if (rvol >= 3) return `volume anormalement fort (${rvol.toFixed(2)}× la moyenne)`
  if (rvol >= 1.5) return `volume confirmé (${rvol.toFixed(2)}× la moyenne)`
  if (rvol >= 1) return `volume proche de la normale (${rvol.toFixed(2)}×)`
  return `participation faible (${rvol.toFixed(2)}× la moyenne)`
}

function ichiPhrase(score: number | null): string {
  if (score == null) return 'score Ichimoku indisponible'
  if (score >= 60) return `structure Ichimoku clairement haussière (score ${score.toFixed(0)})`
  if (score >= 20) return `structure Ichimoku plutôt haussière (score ${score.toFixed(0)})`
  if (score > -20) return `structure Ichimoku neutre / mixte (score ${score.toFixed(0)})`
  if (score > -60) return `structure Ichimoku plutôt baissière (score ${score.toFixed(0)})`
  return `structure Ichimoku clairement baissière (score ${score.toFixed(0)})`
}

function decisionVerb(d: DecisionLabel): string {
  switch (d) {
    case 'STRONG_BUY':
      return 'un signal d’achat fort'
    case 'BUY':
      return 'un signal d’achat'
    case 'WATCH':
      return 'un dossier à surveiller (pas encore d’entrée claire)'
    case 'WAIT':
      return 'd’attendre — pas de signal actionnable'
    case 'SELL':
      return 'un signal de vente'
    case 'STRONG_SELL':
      return 'un signal de vente fort'
    default: {
      const _exhaustive: never = d
      return _exhaustive
    }
  }
}

/**
 * Résumé FR lisible pour le sheet — dérivé des champs déjà renvoyés par le moteur.
 * Aucun appel LLM ; pas d’invention de chiffres.
 */
export function buildDecisionSummary(d: DecisionDetail): string {
  const pair = d.symbol.replace(/USDT$/i, '')
  const confPct = Math.round(d.confidence * 100)
  const agreePct = Math.round(d.agreement * 100)
  const topReasons = d.reasons.slice(0, 3).map(labelReason)
  const reasonsBit =
    topReasons.length > 0 ? ` Principaux points : ${topReasons.join(' ; ')}.` : ''

  const riskBit =
    d.risks.length > 0
      ? ` Attention : ${d.risks.slice(0, 2).map(labelReason).join(' ; ')}.`
      : ''

  return (
    `Sur ${pair} (${d.timeframe}), le moteur voit ${decisionVerb(d.decision)} ` +
    `avec une confiance ${confPhrase(confPct)} (${confPct} %) et un accord entre agents de ${agreePct} %. ` +
    `${ichiPhrase(d.ichimoku_score)}, et ${rvolPhrase(d.rvol)}.` +
    reasonsBit +
    riskBit +
    ` Ce n’est pas un conseil d’investissement : c’est la lecture technique Ichimoku×RVOL au prix ${d.price.toFixed(2)}.`
  )
}

/** Une ligne muted sous une valeur technique (Tenkan, RVOL, BOS…). */
const TERM_HINTS: Record<string, string> = {
  Tenkan: 'Ligne de conversion Ichimoku (//9) — réactivité courte.',
  Kijun: 'Ligne de base Ichimoku (//26) — équilibre moyen.',
  Chikou: 'Prix décalé de 26 barres — confirmation de l’espace libre.',
  Kumo: 'Nuage Ichimoku (Senkou A/B) — zone de support/résistance.',
  RVOL: 'Volume relatif vs moyenne — participation réelle du marché.',
  BOS: 'Break of Structure — cassure de swing dans le sens de la tendance.',
  CHoCH: 'Change of Character — premier retournement de structure.',
  FVG: 'Fair Value Gap — déséquilibre de prix non comblé.',
  R: 'Multiple du risque : distance objectif ÷ distance stop.',
  'walk-forward': 'Validation hors-échantillon glissante — pas un backtest unique.',
  ATR: 'Average True Range — volatilité récente pour placer le stop.',
  VWAP: 'Prix moyen pondéré volume — ancrage intraday.',
  AVWAP: 'VWAP ancré sur un événement (swing, ouverture…).',
  Location: 'Emplacement du prix vs value area / VWAP / nuage.',
  Régime: 'État de volatilité / tradabilité (ATR, tendance).',
}

export function termHint(term: string): string {
  return TERM_HINTS[term] ?? ''
}
