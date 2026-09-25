/**
 * Chantier 2 E1 — data freshness gate before any LLM wake.
 * Uses existing agent_channel get_symbol_context (read-only).
 * Full evaluate_watch_condition DSL → E2.
 */
import * as engineChannel from '../engineAgentChannel.js'

export type FreshnessVerdict =
  | { ok: true; stale: false; dataLate: false }
  | {
      ok: false
      reason: 'stale' | 'data_late' | 'engine_error' | 'missing_symbol'
      stale: boolean
      dataLate: boolean
      detail?: string
    }

type QualityBlob = {
  stale?: boolean | null
  data_late?: boolean | null
  gate?: string | null
  ok?: boolean | null
}

export function freshnessFromContextData(data: unknown): FreshnessVerdict {
  const dq = readQuality(data)
  const stale = dq?.stale === true
  const dataLate = dq?.data_late === true
  const gate = typeof dq?.gate === 'string' ? dq.gate.toLowerCase() : ''
  const gateStale = gate.includes('stale')
  const gateLate = gate.includes('late') || gate.includes('data_late')

  if (stale || gateStale) {
    return { ok: false, reason: 'stale', stale: true, dataLate: dataLate || gateLate }
  }
  if (dataLate || gateLate) {
    return { ok: false, reason: 'data_late', stale: false, dataLate: true }
  }
  return { ok: true, stale: false, dataLate: false }
}

function readQuality(data: unknown): QualityBlob | null {
  if (!data || typeof data !== 'object') return null
  const dq = (data as { data_quality?: QualityBlob }).data_quality
  if (!dq || typeof dq !== 'object') return null
  return dq
}

/**
 * If engine reports stale or data_late → no LLM wake (audit décision Claude).
 */
export async function checkSymbolFreshness(
  symbol: string | null | undefined,
  timeframe: string = '1h',
): Promise<FreshnessVerdict> {
  const sym = symbol?.trim().toUpperCase()
  if (!sym) {
    return { ok: false, reason: 'missing_symbol', stale: false, dataLate: false }
  }

  const res = await engineChannel.engineAgentCommand({
    cmd: 'get_symbol_context',
    args: { symbol: sym, timeframe, persist: false },
  })

  if (!res.ok) {
    return {
      ok: false,
      reason: 'engine_error',
      stale: false,
      dataLate: false,
      detail: res.error,
    }
  }

  return freshnessFromContextData(res.data)
}
