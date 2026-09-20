/** Client des endpoints d'activité : ce que le circuit automatique a fait, et quand. */

export interface ActivitySummary {
  decisions: { total: number; last_24h: number; last_at: string | null }
  paper: {
    opened_total: number
    opened_24h: number
    closed_total: number
    closed_24h: number
    open_now: number
    last_opened_at: string | null
  }
  shadow: { blocked_total: number; blocked_24h: number; judged_total: number }
  backtest: { runs_total: number; last_at: string | null }
  evidence: { rows_total: number }
}

export type FeedTone = 'neutral' | 'good' | 'bad' | 'blocked'

export interface ActivityItem {
  kind: 'paper_opened' | 'paper_closed' | 'shadow_blocked' | 'shadow_closed'
  tone: FeedTone
  symbol: string
  title: string
  detail: string
  time: string
  portfolio: string
}

export interface RunExperiment {
  n_pairs: number
  trades_total: number
  trades_mean: number
  win_rate_mean: number | null
  expectancy_mean: number | null
  sharpe_mean: number | null
  profit_factor_median: number | null
  small_sample: boolean
}

export interface BacktestRun {
  started_at: string
  ended_at: string
  n_rows: number
  n_pairs: number
  experiments: Record<string, RunExperiment>
  pipeline_vs_ichimoku: { beats: number; compared: number }
}

export interface BacktestRuns {
  runs: BacktestRun[]
  total_runs: number
  min_trades_per_pair: number
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path, { credentials: 'include' })
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { detail?: string } | null
    throw new Error(body?.detail ?? `Erreur ${res.status}`)
  }
  return res.json() as Promise<T>
}

export const getActivitySummary = () => getJson<ActivitySummary>('/api/engine/activity/summary')
export const getActivityFeed = (limit = 150) =>
  getJson<{ items: ActivityItem[] }>(`/api/engine/activity/feed?limit=${limit}`)
export const getBacktestRuns = (limit = 30) =>
  getJson<BacktestRuns>(`/api/engine/backtest/runs?limit=${limit}`)

export const EXPERIMENT_LABELS: Record<string, string> = {
  ICHIMOKU_ONLY: 'Ichimoku seul',
  ICHIMOKU_RVOL: 'Ichimoku + RVOL (chaque barre)',
  ICHIMOKU_RVOL_ENTRY_GATE: 'Ichimoku + RVOL (à l’entrée)',
  PIPELINE: 'Pipeline complet',
  PIPELINE_WYCKOFF_FILTER: 'Pipeline + filtre Wyckoff',
}
