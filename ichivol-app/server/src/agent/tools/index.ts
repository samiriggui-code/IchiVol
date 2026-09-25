import type { AgentMode, DecisionContextPayload, LiveContextPayload } from '../types.js'
import { engineAgentBatch } from '../engineAgentChannel.js'
import { mapEngineToDecisionPayload } from './getDecisionDetail.js'
import { getJournalContextTool } from './getJournalContext.js'
import { getLiveSnapshotTool } from './getLiveSnapshot.js'
import { searchKbTool } from './searchKb.js'
import type { ToolResult, ToolRunContext } from './types.js'

export interface ToolOrchestrationResult {
  results: ToolResult[]
  /** Decision pack obtenu via tool (si fetch serveur). */
  decisionFromTool?: DecisionContextPayload
  /** Live pack obtenu via tool. */
  liveFromTool?: LiveContextPayload
  /** Bloc texte injecté dans le system prompt. */
  toolsBlock: string | null
}

function formatToolResults(results: ToolResult[]): string | null {
  if (results.length === 0) return null
  return results
    .map((r) => {
      if (!r.ok) return `[${r.tool}] ERROR: ${r.error}`
      return `[${r.tool}] OK\n${JSON.stringify(r.data, null, 2)}`
    })
    .join('\n\n')
}

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

/**
 * Batch engine : get_symbol_context + compare_timeframes (ordre stable).
 */
async function fetchDecisionBriefBatch(
  symbol: string,
  timeframe: string,
): Promise<{
  context: ToolResult<DecisionContextPayload>
  compare: ToolResult<unknown>
}> {
  const sym = symbol.trim().toUpperCase()
  const tf = timeframe.trim() || '1h'
  const batch = await engineAgentBatch([
    { cmd: 'get_symbol_context', args: { symbol: sym, timeframe: tf, persist: false } },
    {
      cmd: 'compare_timeframes',
      args: { symbol: sym, timeframes: ['15m', '1h', '4h'] },
    },
  ])

  if (!batch.ok) {
    return {
      context: { ok: false, tool: 'get_symbol_context', error: batch.error },
      compare: { ok: false, tool: 'compare_timeframes', error: batch.error },
    }
  }

  const [ctxRes, cmpRes] = batch.results
  let context: ToolResult<DecisionContextPayload>
  if (!ctxRes || !ctxRes.ok) {
    context = {
      ok: false,
      tool: 'get_symbol_context',
      error: ctxRes && !ctxRes.ok ? ctxRes.error : 'missing_result',
    }
  } else {
    const mapped = mapEngineToDecisionPayload(ctxRes.data as EngineDecisionBody, {
      symbol: sym,
      timeframe: tf,
    })
    context = mapped
      ? { ok: true, tool: 'get_symbol_context', data: mapped }
      : {
          ok: false,
          tool: 'get_symbol_context',
          error: 'réponse get_symbol_context incomplète',
        }
  }

  const compare: ToolResult<unknown> =
    cmpRes && cmpRes.ok
      ? { ok: true, tool: 'compare_timeframes', data: cmpRes.data }
      : {
          ok: false,
          tool: 'compare_timeframes',
          error: cmpRes && !cmpRes.ok ? cmpRes.error : 'missing_result',
        }

  return { context, compare }
}

/**
 * MVP E2 : orchestration manuelle par mode (pas de function-calling).
 * Les tools ne recalculent jamais un verdict — canal agent / lecture seule.
 */
export async function runReadOnlyToolsForMode(
  mode: AgentMode,
  ctx: ToolRunContext,
  opts: {
    hasClientDecision: boolean
    hasClientLive: boolean
  },
): Promise<ToolOrchestrationResult> {
  const results: ToolResult[] = []
  let decisionFromTool: DecisionContextPayload | undefined
  let liveFromTool: LiveContextPayload | undefined

  const symbol = ctx.symbol
  const timeframe = ctx.timeframe ?? '1h'

  if (mode === 'explain_decision') {
    if (symbol && !opts.hasClientDecision) {
      const brief = await fetchDecisionBriefBatch(symbol, timeframe)
      results.push(brief.context)
      results.push(brief.compare)
      if (brief.context.ok) decisionFromTool = brief.context.data
    } else if (symbol && opts.hasClientDecision) {
      // Payload client déjà là — enrichir avec multi-TF seulement
      const cmp = await engineAgentBatch([
        {
          cmd: 'compare_timeframes',
          args: { symbol: symbol.trim().toUpperCase(), timeframes: ['15m', '1h', '4h'] },
        },
      ])
      if (!cmp.ok) {
        results.push({ ok: false, tool: 'compare_timeframes', error: cmp.error })
      } else {
        const [row] = cmp.results
        results.push(
          row?.ok
            ? { ok: true, tool: 'compare_timeframes', data: row.data }
            : {
                ok: false,
                tool: 'compare_timeframes',
                error: row && !row.ok ? row.error : 'missing_result',
              },
        )
      }
    }
    const journal = await getJournalContextTool(ctx.userId, symbol)
    results.push(journal)
  }

  if (mode === 'explain_signal') {
    if (!opts.hasClientLive && symbol) {
      const live = await getLiveSnapshotTool(symbol, timeframe)
      results.push(live)
      if (live.ok) liveFromTool = live.data
    }
  }

  // Research avec symbole : prefetch décision + live (évite RAG théorique « aucune donnée »)
  if (mode === 'research' && symbol) {
    if (!opts.hasClientDecision) {
      const brief = await fetchDecisionBriefBatch(symbol, timeframe)
      results.push(brief.context)
      results.push(brief.compare)
      if (brief.context.ok) decisionFromTool = brief.context.data
    }
    if (!opts.hasClientLive) {
      const live = await getLiveSnapshotTool(symbol, timeframe)
      results.push(live)
      if (live.ok) liveFromTool = live.data
    }
  }

  if (mode === 'research' || mode === 'explain_decision' || mode === 'explain_signal') {
    const kb = searchKbTool(ctx.question || `${symbol ?? ''} ${mode}`, 4)
    results.push(kb)
  }

  return {
    results,
    decisionFromTool,
    liveFromTool,
    toolsBlock: formatToolResults(results),
  }
}

export { getDecisionDetailTool } from './getDecisionDetail.js'
export { getLiveSnapshotTool } from './getLiveSnapshot.js'
export { getJournalContextTool } from './getJournalContext.js'
export { searchKbTool } from './searchKb.js'
