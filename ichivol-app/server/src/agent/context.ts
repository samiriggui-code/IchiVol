import type {
  DecisionContextPayload,
  DecisionStagePayload,
  LiveContextPayload,
  ScreenerRowPayload,
} from './types.js'

export function formatLiveContext(live: LiveContextPayload | undefined): string | null {
  if (!live) return null
  const lastSignal = live.lastSignal
    ? `${live.lastSignal.kind} @ ${live.lastSignal.price} (rvol=${live.lastSignal.rvol.toFixed(2)})`
    : 'aucun signal confirmé'

  return [
    `symbole: ${live.symbol}`,
    `intervalle: ${live.interval}`,
    `prix: ${live.price ?? 'inconnu'}`,
    `biais Ichimoku: ${live.bias}`,
    `RVOL actuel: ${live.rvol.toFixed(2)}`,
    `dernier signal: ${lastSignal}`,
  ].join('\n')
}

export function formatScreenerRows(rows: ScreenerRowPayload[] | undefined): string | null {
  if (!rows || rows.length === 0) return null
  return rows
    .slice(0, 10)
    .map(
      (r) =>
        `${r.symbol}: biais=${r.bias}, rvol=${r.rvol.toFixed(2)}, change24h=${r.change24h.toFixed(2)}%, dernier signal=${r.lastSignal ?? 'aucun'}`,
    )
    .join('\n')
}

/** fail → watch → pending → pass → skip → other (impact d’abord, comme SHAP sorted). */
const STAGE_STATUS_RANK: Record<string, number> = {
  fail: 0,
  watch: 1,
  pending: 2,
  pass: 3,
  skip: 4,
}

function stageRank(status: string): number {
  return STAGE_STATUS_RANK[status.toLowerCase()] ?? 5
}

export function sortStagesByImpact(stages: DecisionStagePayload[]): DecisionStagePayload[] {
  return [...stages].sort((a, b) => {
    const byStatus = stageRank(a.status) - stageRank(b.status)
    if (byStatus !== 0) return byStatus
    return a.id.localeCompare(b.id)
  })
}

function formatStageLine(s: DecisionStagePayload): string {
  const codes =
    s.codes && s.codes.length > 0 ? ` codes=[${s.codes.slice(0, 8).join(',')}]` : ''
  return `- ${s.id}: ${s.status} — ${s.summary}${codes}`
}

function formatList(label: string, items: string[] | undefined, max = 12): string | null {
  if (!items || items.length === 0) return null
  return `${label}: ${items.slice(0, max).join(', ')}`
}

/**
 * Evidence pack pour explain_decision (E1).
 * Ordre : verdict → drivers (raisons / risques / invalidation) → portes triées par impact.
 */
export function formatDecisionContext(
  decision: DecisionContextPayload | undefined,
): string | null {
  if (!decision) return null

  const sorted = sortStagesByImpact(decision.stages)
  const stagesBlock =
    sorted.length === 0
      ? '(aucune porte exposée)'
      : sorted.map(formatStageLine).join('\n')

  const blocking = sorted.filter((s) => {
    const st = s.status.toLowerCase()
    return st === 'fail' || st === 'watch'
  })
  const blockingHint =
    blocking.length === 0
      ? 'aucun frein (pas de fail/watch)'
      : blocking.map((s) => `${s.id}=${s.status}`).join(', ')

  const drivers = [
    formatList('raisons (drivers haussiers / baissiers)', decision.reasons),
    formatList('risques', decision.risks),
    formatList('invalidation', decision.invalidation),
  ].filter(Boolean)

  return [
    '=== VERDICT ===',
    `symbole: ${decision.symbol}`,
    `timeframe: ${decision.timeframe}`,
    `prix: ${decision.price ?? 'inconnu'}`,
    `combiner (badge): ${decision.combiner}`,
    `direction: ${decision.direction}`,
    `verdict portes: ${decision.gateDecision ?? 'absent'}`,
    `confidence: ${decision.confidence != null ? decision.confidence.toFixed(3) : 'n/a'}`,
    `RVOL: ${decision.rvol != null ? decision.rvol.toFixed(2) : 'n/a'}`,
    '',
    '=== DRIVERS (citer en priorité dans la prose) ===',
    ...(drivers.length > 0 ? drivers : ['(aucun driver listé)']),
    `freins portes: ${blockingHint}`,
    '',
    '=== PORTES (tri impact: fail → watch → pass) ===',
    stagesBlock,
  ].join('\n')
}
