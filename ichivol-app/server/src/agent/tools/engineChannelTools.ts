import { engineAgentCommand } from '../engineAgentChannel.js'
import type { ToolResult } from './types.js'

/** Résumé multi-TF brut (engine `compare_timeframes`) — lecture seule. */
export async function compareTimeframesTool(
  symbol: string,
  timeframes: string[] = ['15m', '1h', '4h'],
): Promise<ToolResult<unknown>> {
  const tool = 'compare_timeframes'
  const sym = symbol.trim().toUpperCase()
  if (!sym) return { ok: false, tool, error: 'symbol requis' }

  const res = await engineAgentCommand({
    cmd: 'compare_timeframes',
    args: { symbol: sym, timeframes },
  })
  if (!res.ok) {
    return { ok: false, tool, error: res.error }
  }
  return { ok: true, tool, data: res.data }
}

/** Verdict condensé pipeline (`detect_signal`). */
export async function detectSignalTool(
  symbol: string,
  timeframe: string,
): Promise<ToolResult<unknown>> {
  const tool = 'detect_signal'
  const sym = symbol.trim().toUpperCase()
  const tf = timeframe.trim() || '1h'
  if (!sym) return { ok: false, tool, error: 'symbol requis' }

  const res = await engineAgentCommand({
    cmd: 'detect_signal',
    args: { symbol: sym, timeframe: tf },
  })
  if (!res.ok) {
    return { ok: false, tool, error: res.error }
  }
  return { ok: true, tool, data: res.data }
}
