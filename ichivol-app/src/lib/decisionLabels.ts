import type { AgentDirection, DecisionDetail, DecisionLabel, PipelineGateLabel } from './decisions'
import { labelEngineCode, labelEngineCodes } from './engineTerminology'

/** @deprecated Préférer `labelEngineCode` — conservé pour compat. */
export { labelEngineCode as labelReason } from './engineTerminology'
export { labelEngineCodes }

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
  const topReasons = d.reasons.slice(0, 3).map(labelEngineCode)
  const reasonsBit =
    topReasons.length > 0 ? ` Principaux points : ${topReasons.join(' ; ')}.` : ''

  const riskBit =
    d.risks.length > 0
      ? ` Attention : ${d.risks.slice(0, 2).map(labelEngineCode).join(' ; ')}.`
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
