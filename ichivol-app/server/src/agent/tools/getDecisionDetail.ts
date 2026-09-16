import { engineAgentCommand } from '../engineAgentChannel.js'
import { config } from '../../config.js'
import type { DecisionContextPayload } from '../types.js'
import type { ToolResult } from './types.js'

const FETCH_TIMEOUT_MS = 45_000

/** Miroir minimal de la réponse engine (pas de re-score). */
interface EngineDecisionBody {
  symbol?: string
  timeframe?: string
  price?: number
  decision?: string
  direction?: string
  confidence?: number
  rvol?: number | null
  reasons?: string[]
  risks?: string[]
  invalidation?: string[]
  pipeline?: {
    decision?: string
    stages?: Array<{ id?: string; status?: string; summary?: string; codes?: string[] }>
  }
}

export function mapEngineToDecisionPayload(
  body: EngineDecisionBody,
  fallback: { symbol: string; timeframe: string },
): DecisionContextPayload | null {
  const combiner = typeof body.decision === 'string' ? body.decision : null
  const direction = typeof body.direction === 'string' ? body.direction : null
  if (!combiner || !direction) return null

  const stages = (body.pipeline?.stages ?? [])
    .filter(
      (s): s is { id: string; status: string; summary: string; codes?: string[] } =>
        typeof s.id === 'string' &&
        typeof s.status === 'string' &&
        typeof s.summary === 'string',
    )
    .map((s) => ({
      id: s.id,
      status: s.status,
      summary: s.summary,
      codes: Array.isArray(s.codes) ? s.codes.filter((c) => typeof c === 'string') : undefined,
    }))

  return {
    symbol: typeof body.symbol === 'string' ? body.symbol : fallback.symbol,
    timeframe: typeof body.timeframe === 'string' ? body.timeframe : fallback.timeframe,
    price: typeof body.price === 'number' ? body.price : null,
    combiner,
    direction,
    gateDecision:
      typeof body.pipeline?.decision === 'string' ? body.pipeline.decision : null,
    confidence: typeof body.confidence === 'number' ? body.confidence : null,
    rvol: typeof body.rvol === 'number' ? body.rvol : null,
    reasons: Array.isArray(body.reasons) ? body.reasons.filter((r) => typeof r === 'string') : [],
    risks: Array.isArray(body.risks) ? body.risks.filter((r) => typeof r === 'string') : [],
    invalidation: Array.isArray(body.invalidation)
      ? body.invalidation.filter((r) => typeof r === 'string')
      : [],
    stages,
  }
}

async function fetchDecisionViaHttp(
  sym: string,
  tf: string,
): Promise<ToolResult<DecisionContextPayload>> {
  const tool = 'get_decision_detail'
  const url = new URL(
    `${config.engineUrl}/api/engine/decisions/${encodeURIComponent(sym)}`,
  )
  url.searchParams.set('timeframe', tf)
  url.searchParams.set('persist', 'false')

  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(FETCH_TIMEOUT_MS) })
    if (!res.ok) {
      return { ok: false, tool, error: `engine HTTP ${res.status}` }
    }
    const body = (await res.json()) as EngineDecisionBody
    const mapped = mapEngineToDecisionPayload(body, { symbol: sym, timeframe: tf })
    if (!mapped) {
      return { ok: false, tool, error: 'réponse engine incomplète (decision/direction)' }
    }
    return { ok: true, tool, data: mapped }
  } catch (err) {
    const message = err instanceof Error ? err.message : 'engine unreachable'
    return { ok: false, tool, error: message }
  }
}

/**
 * Read-only : détail décision via canal agent `get_symbol_context`.
 * Fallback HTTP `GET /decisions/{symbol}` si la commande échoue.
 * Ne recalcule / ne vote rien.
 */
export async function getDecisionDetailTool(
  symbol: string,
  timeframe: string,
): Promise<ToolResult<DecisionContextPayload>> {
  const tool = 'get_symbol_context'
  const sym = symbol.trim().toUpperCase()
  const tf = timeframe.trim() || '1h'
  if (!sym) return { ok: false, tool, error: 'symbol requis' }

  const channel = await engineAgentCommand({
    cmd: 'get_symbol_context',
    args: { symbol: sym, timeframe: tf, persist: false },
  })

  if (channel.ok) {
    const mapped = mapEngineToDecisionPayload(
      channel.data as EngineDecisionBody,
      { symbol: sym, timeframe: tf },
    )
    if (mapped) {
      return { ok: true, tool, data: mapped }
    }
    return { ok: false, tool, error: 'réponse get_symbol_context incomplète' }
  }

  // Fallback legacy route (même payload) — ex. engine trop ancien
  const fallback = await fetchDecisionViaHttp(sym, tf)
  if (fallback.ok) {
    return { ok: true, tool: 'get_decision_detail', data: fallback.data }
  }
  return {
    ok: false,
    tool,
    error: `${channel.error}; fallback: ${fallback.error}`,
  }
}
