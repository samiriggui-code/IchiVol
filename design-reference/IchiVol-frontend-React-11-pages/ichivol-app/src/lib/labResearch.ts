/** Strategy Lab Research clients — T5b / T6 / T7 / Researcher (observation only). */

async function parseError(res: Response): Promise<string> {
  const body = (await res.json().catch(() => null)) as
    | { detail?: string; message?: string; error?: string }
    | null
  return body?.detail ?? body?.message ?? body?.error ?? `Erreur ${res.status}`
}

export interface FamilyWeightProfileRow {
  id: string
  label: string
  description: string
  version: string
  weights: Record<string, number>
}

export interface FamilyWeightProfilesResult {
  profiles: FamilyWeightProfileRow[]
  disclaimer: string
}

export async function listFamilyWeightProfiles(): Promise<FamilyWeightProfilesResult> {
  const res = await fetch('/api/engine/strategy-lab/family-weight-profiles', {
    credentials: 'include',
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<FamilyWeightProfilesResult>
}

export interface FamilyWeightCompareProfile {
  id: string
  label: string
  description: string
  version: string
  weights: Record<string, number>
  family_status: Record<string, string>
  family_contribution: Record<string, number>
  weighted_support: number
}

export interface FamilyWeightCompareResult {
  symbol: string
  timeframe: string
  decision: string
  confidence: number
  pipeline_decision: string
  disclaimer: string
  profiles: Record<string, FamilyWeightCompareProfile>
}

export async function compareFamilyWeights(
  symbol: string,
  timeframe = '1h',
  limit = 300,
): Promise<FamilyWeightCompareResult> {
  const params = new URLSearchParams({
    symbol,
    timeframe,
    limit: String(limit),
  })
  const res = await fetch(
    `/api/engine/strategy-lab/family-weights/compare?${params}`,
    { credentials: 'include' },
  )
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<FamilyWeightCompareResult>
}

export interface FamilyWeightStudyAggregate {
  profile_id: string
  n_signals: number
  mean_support: number
  mean_forward?: Record<string, number | null>
}

export interface FamilyWeightStudyResult {
  symbol: string
  timeframe: string
  n_bars: number
  n_signals: number
  profile_ids: string[]
  aggregates: FamilyWeightStudyAggregate[]
  disclaimer: string
}

export async function runFamilyWeightsStudy(
  symbol: string,
  timeframe = '1h',
  limit = 500,
): Promise<FamilyWeightStudyResult> {
  const params = new URLSearchParams({
    symbol,
    timeframe,
    limit: String(limit),
    step: '1',
    sample_limit: '20',
  })
  const res = await fetch(
    `/api/engine/strategy-lab/family-weights/study?${params}`,
    { credentials: 'include' },
  )
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<FamilyWeightStudyResult>
}

export interface AuditHypothesis {
  id: string
  statement: string
  suggested_experiment: string
  status: string
}

export interface AuditReportResult {
  version: string
  symbol: string
  timeframe: string
  ruleset_id: string | null
  trade_index: number
  outcome: Record<string, unknown>
  what_worked: string[]
  what_failed: string[]
  hypotheses: AuditHypothesis[]
  disclaimer: string
  n_trades?: number
}

export async function buildAuditReport(opts: {
  symbol: string
  timeframe?: string
  limit?: number
  rulesetId: string
  tradeIndex?: number
}): Promise<AuditReportResult> {
  const res = await fetch('/api/engine/strategy-lab/audit-report', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      symbol: opts.symbol,
      timeframe: opts.timeframe ?? '1h',
      limit: opts.limit ?? 300,
      ruleset_id: opts.rulesetId,
      trade_index: opts.tradeIndex ?? 0,
    }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<AuditReportResult>
}

export interface MonteCarloResult {
  version: string
  symbol: string
  timeframe: string
  ruleset_id: string | null
  n_trades: number
  n_paths: number
  sufficient: boolean
  mean_final_equity: number | null
  p05_final_equity: number | null
  p50_final_equity: number | null
  p95_final_equity: number | null
  mean_max_drawdown: number | null
  p95_max_drawdown: number | null
  risk_of_ruin: number | null
  disclaimer: string
}

export async function runMonteCarlo(opts: {
  symbol: string
  timeframe?: string
  limit?: number
  rulesetId: string
  nPaths?: number
  minTrades?: number
}): Promise<MonteCarloResult> {
  const res = await fetch('/api/engine/strategy-lab/monte-carlo', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      symbol: opts.symbol,
      timeframe: opts.timeframe ?? '1h',
      limit: opts.limit ?? 1000,
      ruleset_id: opts.rulesetId,
      n_paths: opts.nPaths ?? 1000,
      min_trades: opts.minTrades ?? 20,
      seed: 42,
    }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<MonteCarloResult>
}

export interface ExperimentPlanStep {
  tool: string
  args: Record<string, unknown>
  purpose: string
}

export interface ExperimentPlanResult {
  version: string
  status: string
  source_hypothesis_ids: string[]
  symbol: string
  timeframe: string
  ruleset_id: string | null
  steps: ExperimentPlanStep[]
  notes: string[]
  disclaimer: string
}

export async function proposeExperimentPlan(
  auditReport: AuditReportResult | Record<string, unknown>,
  hypothesisIds?: string[],
): Promise<ExperimentPlanResult> {
  const res = await fetch('/api/engine/strategy-lab/propose-experiment-plan', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      audit_report: auditReport,
      hypothesis_ids: hypothesisIds,
    }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<ExperimentPlanResult>
}
