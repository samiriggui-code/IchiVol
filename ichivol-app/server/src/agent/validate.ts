import type { AgentChatRequest, DecisionContextPayload } from './types.js'

const MODES = new Set(['explain_signal', 'research', 'trade_idea', 'explain_decision'])
const BIASES = new Set(['bull', 'bear', 'neutral'])
const PROVIDERS = new Set(['anthropic', 'openai', 'openrouter'])
const DIRECTIONS = new Set(['LONG', 'SHORT', 'NEUTRAL'])
const STAGE_STATUSES = new Set(['pass', 'fail', 'watch', 'pending', 'skip'])

function isFullDecision(d: DecisionContextPayload): boolean {
  return (
    typeof d.combiner === 'string' &&
    d.combiner.trim().length > 0 &&
    typeof d.direction === 'string' &&
    DIRECTIONS.has(d.direction) &&
    Array.isArray(d.stages)
  )
}

/** True si on a assez d'info pour que le serveur fetch via tools (E2). */
export function canResolveDecisionViaTools(b: Partial<AgentChatRequest>): boolean {
  if (b.decision && typeof b.decision.symbol === 'string' && b.decision.symbol.trim()) {
    return true
  }
  if (typeof b.symbol === 'string' && b.symbol.trim()) return true
  if (b.live && typeof b.live.symbol === 'string' && b.live.symbol.trim()) return true
  return false
}

export function resolveSymbolTimeframe(b: Partial<AgentChatRequest>): {
  symbol?: string
  timeframe: string
} {
  const symbol =
    (typeof b.decision?.symbol === 'string' && b.decision.symbol.trim()) ||
    (typeof b.symbol === 'string' && b.symbol.trim()) ||
    (typeof b.live?.symbol === 'string' && b.live.symbol.trim()) ||
    undefined
  const timeframe =
    (typeof b.decision?.timeframe === 'string' && b.decision.timeframe.trim()) ||
    (typeof b.timeframe === 'string' && b.timeframe.trim()) ||
    (typeof b.live?.interval === 'string' && b.live.interval.trim()) ||
    '1h'
  return {
    symbol: symbol ? symbol.toUpperCase() : undefined,
    timeframe,
  }
}

export function validateAgentChatRequest(body: unknown): string | null {
  if (typeof body !== 'object' || body === null) return 'body invalide'
  const b = body as Partial<AgentChatRequest>

  if (!MODES.has(b.mode as string)) return 'mode invalide'
  if (typeof b.question !== 'string') return 'question manquante'

  if (b.provider !== undefined && !PROVIDERS.has(b.provider)) return 'provider invalide'

  if (b.live !== undefined) {
    const live = b.live
    if (typeof live.symbol !== 'string' || typeof live.interval !== 'string') {
      return 'live.symbol/interval invalides'
    }
    if (live.price !== null && !Number.isFinite(live.price)) return 'live.price invalide'
    if (!BIASES.has(live.bias)) return 'live.bias invalide'
    if (!Number.isFinite(live.rvol)) return 'live.rvol invalide'
  }

  if (b.screenerRows !== undefined) {
    if (!Array.isArray(b.screenerRows)) return 'screenerRows invalide'
    for (const row of b.screenerRows) {
      if (typeof row.symbol !== 'string' || !Number.isFinite(row.rvol) || !Number.isFinite(row.change24h)) {
        return 'screenerRows contient une ligne invalide'
      }
    }
  }

  if (b.mode === 'explain_decision') {
    const hasFull = b.decision != null && isFullDecision(b.decision)
    if (!hasFull && !canResolveDecisionViaTools(b)) {
      return 'decision complète ou symbol requis pour explain_decision'
    }
  }

  if (b.decision !== undefined) {
    const d = b.decision
    if (typeof d.symbol !== 'string' || !d.symbol.trim()) return 'decision.symbol invalide'
    if (typeof d.timeframe !== 'string' || !d.timeframe.trim()) {
      return 'decision.timeframe invalide'
    }
    // Pack partiel OK (E2 tools complètent) — valider le reste seulement si full.
    if (isFullDecision(d)) {
      if (!DIRECTIONS.has(d.direction)) return 'decision.direction invalide'
      if (d.price != null && !Number.isFinite(d.price)) return 'decision.price invalide'
      if (d.confidence != null && !Number.isFinite(d.confidence)) {
        return 'decision.confidence invalide'
      }
      if (d.rvol != null && !Number.isFinite(d.rvol)) return 'decision.rvol invalide'
      for (const s of d.stages) {
        if (typeof s.id !== 'string' || typeof s.status !== 'string' || typeof s.summary !== 'string') {
          return 'decision.stages entrée invalide'
        }
        if (!STAGE_STATUSES.has(s.status)) return 'decision.stages status invalide'
      }
    }
  }

  return null
}

export function hasFullClientDecision(b: Partial<AgentChatRequest>): boolean {
  return b.decision != null && isFullDecision(b.decision)
}
