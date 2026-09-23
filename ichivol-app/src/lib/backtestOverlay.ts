/** T4a — POST /strategy-lab/backtest-overlay client. */

import type { ChartObject } from './chartObjects'
import type { BacktestMetrics } from './backtest'

export type BacktestOutcomeFilter = 'all' | 'win' | 'loss'

export interface BacktestOverlayTrade {
  trade_id: number
  direction: string
  entry_time: number
  exit_time: number
  entry_price: number
  exit_price: number
  exit_reason: string
  return_pct: number
  r_multiple: number
  outcome: 'win' | 'loss' | 'flat'
}

export interface BacktestOverlayCounts {
  total: number
  win: number
  loss: number
  flat: number
}

export interface BacktestOverlayResult {
  symbol: string
  timeframe: string
  ruleset_id: string
  outcome_filter: BacktestOutcomeFilter
  objects: ChartObject[]
  trades: BacktestOverlayTrade[]
  metrics: BacktestMetrics
  counts: BacktestOverlayCounts
  n_signals: number
  n_skipped_in_position: number
}

export async function postBacktestOverlay(input: {
  symbol: string
  timeframe: string
  limit?: number
  ruleset_id: string
  outcome?: BacktestOutcomeFilter
}): Promise<BacktestOverlayResult> {
  const res = await fetch('/api/engine/strategy-lab/backtest-overlay', {
    method: 'POST',
    credentials: 'include',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      symbol: input.symbol,
      timeframe: input.timeframe,
      limit: input.limit ?? 300,
      ruleset_id: input.ruleset_id,
      outcome: input.outcome ?? 'all',
    }),
  })
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { detail?: string } | null
    throw new Error(body?.detail ?? `Erreur ${res.status}`)
  }
  return (await res.json()) as BacktestOverlayResult
}
