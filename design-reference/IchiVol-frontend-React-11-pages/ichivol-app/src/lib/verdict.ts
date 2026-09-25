import type { DecisionLabel, PipelineGateLabel } from './decisions'

/**
 * Source unique pour la règle Option B (docs/OPTIONS-ABC.md) : le verdict
 * qui compte pour agir est celui des portes (pipeline.decision) quand il
 * est disponible ; le combiner legacy (Ichimoku x RVOL) redescend en
 * diagnostic secondaire. Avant ce fichier, chaque écran réimplémentait sa
 * propre version de asGate/gateTone/decisionTone — d'où la dérive Table /
 * Overview restées en esprit Option A pendant que la Matrice était déjà en B.
 */

export function decisionTone(decision: DecisionLabel | string): 'bull' | 'bear' | 'neutral' {
  if (decision === 'STRONG_BUY' || decision === 'BUY') return 'bull'
  if (decision === 'STRONG_SELL' || decision === 'SELL') return 'bear'
  return 'neutral'
}

export function gateTone(gate: PipelineGateLabel | null): 'bull' | 'bear' | 'neutral' {
  if (gate === 'BUY') return 'bull'
  if (gate === 'SELL') return 'bear'
  return 'neutral'
}

export function asGate(raw: string | undefined | null): PipelineGateLabel | null {
  if (raw === 'BUY' || raw === 'SELL' || raw === 'WATCH' || raw === 'NO_TRADE') return raw
  return null
}
