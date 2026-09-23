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

/** Collecte auto condition 1 — lecture seule, jamais une promotion de porte. */
export interface BacktestEvidenceSummary {
  enabled: boolean
  interval_s: number
  total_rows: number
  /** Lancements de collecte distincts (total_rows = résultats, pas lancements). */
  runs_total?: number
  last_run_at: string | null
  first_run_at: string | null
  distinct_days: number
  latest_pairs: number
  pipeline_beats_ichimoku_sharpe: { beats: number; compared: number } | null
  note: string | null
}

export async function getBacktestEvidence(): Promise<BacktestEvidenceSummary> {
  const res = await fetch('/api/engine/backtest/evidence', {
    credentials: 'include',
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<BacktestEvidenceSummary>
}

/** Strategy Lab Phase 1 — forward path after signals, no capital sim. */
export interface EventStudyHorizonStats {
  horizon: number
  n: number
  mean_atr: number | null
  median_atr: number | null
  mean_pct: number | null
}

export interface EventStudyResult {
  symbol: string
  timeframe: string
  variant: string
  n_bars: number
  n_events: number
  horizons: number[]
  r_multiple: number
  horizon_stats: EventStudyHorizonStats[]
  mean_mfe_atr: number | null
  mean_mae_atr: number | null
  median_mfe_atr: number | null
  median_mae_atr: number | null
  pct_hit_plus_r_before_minus_r: number | null
  n_resolved_r: number
  note: string
}

export async function getEventStudy(
  symbol: string,
  timeframe = '1h',
  limit = 1000,
  variant: ExperimentName | 'PIPELINE_WYCKOFF_FILTER' = 'PIPELINE',
): Promise<EventStudyResult> {
  const params = new URLSearchParams({
    timeframe,
    limit: String(limit),
    variant,
    horizons: '1,3,5,10',
    r_multiple: '1',
  })
  const res = await fetch(
    `/api/engine/event-study/${encodeURIComponent(symbol)}?${params}`,
    { credentials: 'include' },
  )
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<EventStudyResult>
}

export interface RulesetSummary {
  id: string
  version: string
  direction: string
  description: string
  conditions: Record<string, boolean | number>
  entry: string
  stop_atr: number
  target_atr: number
}

export interface StoredExperimentSummary {
  experiment_id: string
  ruleset_id: string
  symbol: string
  timeframe: string
  market_regime?: string
  number_of_trades: number
  win_rate: number | null
  profit_factor: number | null
  expectancy: number | null
  sharpe: number | null
  max_drawdown: number | null
  mean_mfe_atr: number | null
  mean_mae_atr: number | null
  created_at: string | null
}

export interface RulesetStudyResult {
  ruleset: RulesetSummary
  symbol: string
  timeframe: string
  n_bars: number
  n_matching_bars: number
  n_signals: number
  event_study: EventStudyResult
  backtest?: {
    metrics: BacktestMetrics
    n_signals: number
    n_skipped_in_position: number
    exit_reasons: Record<string, number>
  }
  experiment?: StoredExperimentSummary & Record<string, unknown>
  note: string
}

export async function listRulesets(): Promise<{
  rulesets: RulesetSummary[]
  condition_keys: string[]
}> {
  const res = await fetch('/api/engine/rulesets', { credentials: 'include' })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<{ rulesets: RulesetSummary[]; condition_keys: string[] }>
}

export async function getRulesetEventStudy(
  rulesetId: string,
  symbol: string,
  timeframe = '1h',
  limit = 1000,
  persist = true,
): Promise<RulesetStudyResult> {
  const params = new URLSearchParams({
    symbol,
    timeframe,
    limit: String(limit),
    horizons: '1,3,5,10',
    persist: persist ? 'true' : 'false',
  })
  const res = await fetch(
    `/api/engine/ruleset/${encodeURIComponent(rulesetId)}/event-study?${params}`,
    { credentials: 'include' },
  )
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<RulesetStudyResult>
}

export async function listStoredExperiments(opts?: {
  symbol?: string
  timeframe?: string
  ruleset_id?: string
  market_regime?: string
  limit?: number
}): Promise<{ experiments: StoredExperimentSummary[]; count: number }> {
  const params = new URLSearchParams()
  if (opts?.symbol) params.set('symbol', opts.symbol)
  if (opts?.timeframe) params.set('timeframe', opts.timeframe)
  if (opts?.ruleset_id) params.set('ruleset_id', opts.ruleset_id)
  if (opts?.market_regime) params.set('market_regime', opts.market_regime)
  params.set('limit', String(opts?.limit ?? 20))
  const res = await fetch(`/api/engine/strategy-lab/experiments?${params}`, {
    credentials: 'include',
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<{ experiments: StoredExperimentSummary[]; count: number }>
}

export async function getStoredExperiment(
  experimentId: string,
): Promise<StoredExperimentSummary & Record<string, unknown>> {
  const res = await fetch(
    `/api/engine/strategy-lab/experiments/${encodeURIComponent(experimentId)}`,
    { credentials: 'include' },
  )
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<StoredExperimentSummary & Record<string, unknown>>
}

/** Latest persisted run per ruleset_id (Performance DB — no live recompute). */
export async function compareStoredRulesets(opts: {
  symbol: string
  timeframe?: string
  ruleset_ids: string[]
  market_regime?: string
}): Promise<{
  symbol: string
  timeframe: string
  market_regime: string
  experiments: StoredExperimentSummary[]
}> {
  const params = new URLSearchParams({
    symbol: opts.symbol,
    timeframe: opts.timeframe ?? '1h',
    ruleset_ids: opts.ruleset_ids.join(','),
    market_regime: opts.market_regime ?? 'GLOBAL',
  })
  const res = await fetch(`/api/engine/strategy-lab/compare?${params}`, {
    credentials: 'include',
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<{
    symbol: string
    timeframe: string
    market_regime: string
    experiments: StoredExperimentSummary[]
  }>
}

export interface AblationDelta {
  from_label: string
  to_label: string
  added_conditions: string[]
  n_signals_delta: number
  n_trades_delta: number
  win_rate_delta: number | null
  profit_factor_delta: number | null
  expectancy_delta: number | null
  max_drawdown_delta: number | null
  sharpe_delta: number | null
  improves_expectancy: boolean | null
  improves_profit_factor: boolean | null
  note: string
}

export interface AblationStepRow {
  label: string
  n_signals: number
  n_matching_bars: number
  study: RulesetStudyResult
  experiment_id: string | null
}

export interface AblationResult {
  symbol: string
  timeframe: string
  mode: string
  n_bars: number
  steps: AblationStepRow[]
  deltas: AblationDelta[]
  note: string
}

export async function getAblation(
  symbol: string,
  timeframe = '1h',
  limit = 1000,
  persist = false,
): Promise<AblationResult> {
  const params = new URLSearchParams({
    symbol,
    timeframe,
    limit: String(limit),
    mode: 'cumulative',
    direction: 'LONG',
    persist: persist ? 'true' : 'false',
  })
  const res = await fetch(`/api/engine/strategy-lab/ablation?${params}`, {
    credentials: 'include',
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<AblationResult>
}

export interface RegimeSliceRow {
  regime: string
  n_signals: number
  n_bars_in_regime: number
  experiment_id: string | null
  study: RulesetStudyResult
}

export interface RegimeSlicesResult {
  symbol: string
  timeframe: string
  ruleset: RulesetSummary
  n_bars: number
  regime_bar_counts: Record<string, number>
  slices: RegimeSliceRow[]
  note: string
}

export async function getRegimeSlices(
  symbol: string,
  timeframe = '1h',
  limit = 1000,
  rulesetId = 'IV_ICHIMOKU_RVOL_LONG_001',
  persist = false,
): Promise<RegimeSlicesResult> {
  const params = new URLSearchParams({
    symbol,
    timeframe,
    limit: String(limit),
    ruleset_id: rulesetId,
    persist: persist ? 'true' : 'false',
  })
  const res = await fetch(`/api/engine/strategy-lab/regime-slices?${params}`, {
    credentials: 'include',
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<RegimeSlicesResult>
}

export interface WalkForwardFoldRow {
  fold_index: number
  train_start: number
  train_end: number
  test_start: number
  test_end: number
  train_bars: number
  test_bars: number
  train_experiment_id: string | null
  test_experiment_id: string | null
  is: RulesetStudyResult | null
  oos: RulesetStudyResult
}

export interface WalkForwardResult {
  symbol: string
  timeframe: string
  ruleset: RulesetSummary
  mode: string
  n_bars: number
  warmup_bars: number
  train_bars: number
  test_bars: number
  step_bars: number
  folds: WalkForwardFoldRow[]
  oos_summary: {
    n_folds: number
    folds_with_trades: number
    mean_oos_expectancy: number | null
    mean_oos_profit_factor: number | null
    mean_oos_sharpe: number | null
    pct_folds_pf_gt_1: number | null
    pct_folds_expectancy_gt_0: number | null
    total_oos_trades: number
  }
  note: string
}

export async function getWalkForward(
  symbol: string,
  timeframe = '1h',
  limit = 1000,
  rulesetId = 'IV_ICHIMOKU_RVOL_LONG_001',
  opts?: {
    mode?: 'rolling' | 'expanding'
    trainBars?: number
    testBars?: number
    persist?: boolean
  },
): Promise<WalkForwardResult> {
  const trainBars =
    opts?.trainBars ?? Math.max(50, Math.min(400, Math.floor(limit * 0.5)))
  const testBars =
    opts?.testBars ?? Math.max(20, Math.min(100, Math.floor(limit * 0.15)))
  const params = new URLSearchParams({
    symbol,
    timeframe,
    limit: String(limit),
    ruleset_id: rulesetId,
    mode: opts?.mode ?? 'rolling',
    train_bars: String(trainBars),
    test_bars: String(testBars),
    include_train: 'true',
    persist: opts?.persist ? 'true' : 'false',
  })
  const res = await fetch(`/api/engine/strategy-lab/walk-forward?${params}`, {
    credentials: 'include',
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<WalkForwardResult>
}

export interface WalkForwardOptFoldRow {
  fold_index: number
  train_start: number
  train_end: number
  test_start: number
  test_end: number
  train_bars: number
  test_bars: number
  best_params: Record<string, number>
  is_score: number | null
  is_n_trades: number
  n_candidates_scored: number
  train_experiment_id: string | null
  test_experiment_id: string | null
  is: RulesetStudyResult | null
  oos: RulesetStudyResult
}

export interface WalkForwardOptResult {
  symbol: string
  timeframe: string
  base_ruleset: RulesetSummary
  mode: string
  objective: string
  min_trades: number
  grid: Record<string, number[]>
  n_bars: number
  train_bars: number
  test_bars: number
  folds: WalkForwardOptFoldRow[]
  oos_summary: WalkForwardResult['oos_summary']
  param_stability: {
    n_folds: number
    keys: Record<
      string,
      { mode: string; counts: Record<string, number>; unique: number }
    >
  }
  note: string
}

/** Compact default grid for UI (keeps latency reasonable). */
const UI_OPT_GRID: Record<string, number[]> = {
  rvol_min: [1.2, 1.5, 2.0],
  tk_cross_age_max: [2, 3, 5],
  stop_atr: [1.0, 1.5],
  target_atr: [2.0, 3.0],
}

export async function getWalkForwardOpt(
  symbol: string,
  timeframe = '1h',
  limit = 1000,
  rulesetId = 'IV_ICHIMOKU_RVOL_LONG_001',
  opts?: {
    mode?: 'rolling' | 'expanding'
    trainBars?: number
    testBars?: number
    objective?: 'expectancy' | 'profit_factor' | 'sharpe'
    minTrades?: number
    persist?: boolean
    grid?: Record<string, number[]>
  },
): Promise<WalkForwardOptResult> {
  const trainBars =
    opts?.trainBars ?? Math.max(50, Math.min(400, Math.floor(limit * 0.5)))
  const testBars =
    opts?.testBars ?? Math.max(20, Math.min(100, Math.floor(limit * 0.15)))
  const res = await fetch('/api/engine/strategy-lab/walk-forward-opt', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      symbol,
      timeframe,
      limit,
      ruleset_id: rulesetId,
      mode: opts?.mode ?? 'rolling',
      train_bars: trainBars,
      test_bars: testBars,
      objective: opts?.objective ?? 'expectancy',
      min_trades: opts?.minTrades ?? 3,
      persist: opts?.persist ?? false,
      grid: opts?.grid ?? UI_OPT_GRID,
    }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<WalkForwardOptResult>
}
