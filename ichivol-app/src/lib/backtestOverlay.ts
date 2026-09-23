/** T4a/T4c — POST /strategy-lab/backtest-overlay client. */

import type { ChartObject } from './chartObjects'
import type { BacktestMetrics } from './backtest'

export type BacktestOutcomeFilter = 'all' | 'win' | 'loss'

export interface ConditionLeafTrace {
  key: string
  clause: 'all' | 'any' | string
  expected: unknown
  passed: boolean
}

export interface BacktestOverlayTrade {
  trade_id: number
  direction: string
  entry_time: number
  exit_time: number
  entry_price: number
  exit_price: number
  exit_reason: string
  return_pct_gross: number
  return_pct_net: number
  r_multiple_gross: number
  outcome: 'win' | 'loss' | 'flat'
  signal_index?: number
  why_entered?: ConditionLeafTrace[]
  why_exited?: ConditionLeafTrace[]
  regime_labels?: string[]
}

export interface BacktestRejectedSignal {
  rejected_id: number
  signal_index: number
  signal_time: number | null
  direction: string
  reason: string
  why_entered: ConditionLeafTrace[]
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
  rejected: BacktestRejectedSignal[]
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
  exit_reason?: string | null
  direction?: string | null
  why_entered_key?: string | null
  regime_label?: string | null
  include_rejected?: boolean
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
      exit_reason: input.exit_reason || undefined,
      direction: input.direction || undefined,
      why_entered_key: input.why_entered_key || undefined,
      regime_label: input.regime_label || undefined,
      include_rejected: input.include_rejected ?? true,
    }),
  })
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { detail?: string } | null
    throw new Error(body?.detail ?? `Erreur ${res.status}`)
  }
  return (await res.json()) as BacktestOverlayResult
}
