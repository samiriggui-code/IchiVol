import { appendEngineThresholds, loadEngineThresholds } from './engineThresholds'
import type { AgentDirection } from './decisions'

export type ExperimentName =
  | 'ICHIMOKU_ONLY'
  | 'ICHIMOKU_RVOL'
  | 'ICHIMOKU_RVOL_ENTRY_GATE'
  | 'PIPELINE'

export interface BacktestTrade {
  entry_time: number
  exit_time: number
  direction: AgentDirection
  entry_price: number
  exit_price: number
  pnl_pct: number
}

export interface BacktestMetrics {
  n_bars: number
  total_return: number
  cagr: number | null
  sharpe: number | null
  sortino: number | null
  max_drawdown: number
  num_trades: number
  win_rate: number | null
  profit_factor: number | null
  expectancy: number | null
  exposure: number
}

export interface BacktestRunDetail {
  symbol: string
  timeframe: string
  n_bars: number
  commission_bps: number
  slippage_bps: number
  trades: BacktestTrade[]
}

export interface ExperimentResult {
  metrics: BacktestMetrics
  backtest: BacktestRunDetail
}

export interface BacktestComparison {
  symbol: string
  timeframe: string
  experiments: Partial<Record<ExperimentName, ExperimentResult>>
}

async function parseError(res: Response): Promise<string> {
  const body = (await res.json().catch(() => null)) as
    | { detail?: string; message?: string; error?: string }
    | null
  return body?.detail ?? body?.message ?? body?.error ?? `Erreur ${res.status}`
}

export async function getBacktestComparison(
  symbol: string,
  timeframe = '1h',
  limit = 1000,
): Promise<BacktestComparison> {
  const params = new URLSearchParams({
    timeframe,
    limit: String(limit),
  })
  appendEngineThresholds(params, await loadEngineThresholds())
  const res = await fetch(
    `/api/engine/backtest/${encodeURIComponent(symbol)}?${params}`,
    { credentials: 'include' },
  )
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<BacktestComparison>
}
