import type { LiveContextPayload } from '../types.js'
import { getDecisionDetailTool } from './getDecisionDetail.js'
import type { ToolResult } from './types.js'

function directionToBias(direction: string): LiveContextPayload['bias'] {
  if (direction === 'LONG') return 'bull'
  if (direction === 'SHORT') return 'bear'
  return 'neutral'
}

/**
 * Snapshot « live » dérivé du détail moteur (read-only).
 * Pas de second score — biais = direction engine, RVOL = champ moteur.
 */
export async function getLiveSnapshotTool(
  symbol: string,
  timeframe: string,
): Promise<ToolResult<LiveContextPayload>> {
  const tool = 'get_live_snapshot'
  const detail = await getDecisionDetailTool(symbol, timeframe)
  if (!detail.ok) {
    return { ok: false, tool, error: detail.error }
  }
  const d = detail.data
  return {
    ok: true,
    tool,
    data: {
      symbol: d.symbol,
      interval: d.timeframe,
      price: d.price ?? null,
      bias: directionToBias(d.direction),
      rvol: d.rvol ?? 0,
      lastSignal: null,
    },
  }
}
