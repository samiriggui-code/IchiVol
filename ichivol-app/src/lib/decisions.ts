import { appendEngineThresholds, loadEngineThresholds } from './engineThresholds'
import type { OrderIntent } from './paper'
import type { LabContextPayload } from './types'

export type DecisionLabel = 'STRONG_BUY' | 'BUY' | 'WATCH' | 'WAIT' | 'SELL' | 'STRONG_SELL'
export type AgentDirection = 'LONG' | 'SHORT' | 'NEUTRAL'

/** Verdict portes north star (pipeline.decision) — parallèle au DecisionLabel legacy. */
export type PipelineGateLabel = 'BUY' | 'SELL' | 'WATCH' | 'NO_TRADE'

/** Miroir du contrat pipeline (détail dans decisionPipeline.ts). Évite import circulaire. */
export interface DecisionPipelinePayload {
  decision?: PipelineGateLabel | string
  direction?: AgentDirection
  strategy_version?: string
  stages: Array<{
    id: 'direction' | 'participation' | 'structure' | 'location' | 'regime'
    status: 'pass' | 'fail' | 'watch' | 'pending' | 'skip'
    summary: string
    codes?: string[]
  }>
}

/** T11a — observation qualité bougies (screener summary). */
export interface ScreenerDataQuality {
  version?: string
  ok?: boolean
  gate?: string
  issue_codes?: string[]
  stale?: boolean
  data_late?: boolean
}

export interface ScreenerDecisionRow {
  symbol: string
  timeframe: string
  price: number
  decision: DecisionLabel
  direction: AgentDirection
  confidence: number
  probability: number
  ichimoku_score: number | null
  rvol: number | null
  /** Présent sur chaque ligne screener (même contrat que le détail). */
  pipeline?: DecisionPipelinePayload
  /** T9f Lab snapshot — observation only (watchlist Contexte badges). */
  lab_context?: LabContextPayload
  /** T11a — stale / data_late pour notice fraîcheur Desk. */
  data_quality?: ScreenerDataQuality | null
}

export interface AgentDetail {
  direction: AgentDirection
  confidence: number
  probability?: number
  reasons: string[]
  metadata: Record<string, unknown>
}

export interface EvidenceHistorical {
  sample_size: number
  sample_quality: string
  status: string
  horizon: number
  mean_return_pct: number | null
  median_return_pct: number | null
  favorable_rate: number | null
  mean_mfe_pct: number | null
  mean_mae_pct: number | null
}

export interface EvidenceAblationRow {
  label: string
  sample_size: number
  favorable_rate: number | null
  mean_return_pct: number | null
  median_return_pct: number | null
}

export interface EvidencePack {
  evidence_engine_version?: string
  rules_version?: string
  feature_version?: string
  strategy_version?: string
  calibration_note?: string
  historical?: EvidenceHistorical
  ablation?: EvidenceAblationRow[]
  positive_evidence?: string[]
  contradictions?: string[]
  invalidation?: string[]
  why_not_long?: string[]
  why_not_short?: string[]
  context?: Record<string, unknown>
}

export interface DecisionDetail extends ScreenerDecisionRow {
  reasons: string[]
  risks: string[]
  invalidation: string[]
  positive_evidence?: string[]
  contradictions?: string[]
  why_not?: string[]
  agreement: number
  weights_used: Record<string, unknown>
  strategy_version: string
  timestamp: number
  volume_type?: string
  ichimoku: AgentDetail
  rvol_detail: AgentDetail & { volume_type?: string }
  /** Présent quand le moteur expose le pipeline à portes (V1+). */
  pipeline?: DecisionPipelinePayload
  evidence?: EvidencePack
  context?: Record<string, unknown>
  /** Intent paper (qty/stop/TP) — suggest before act */
  order_intent?: OrderIntent | null
}

async function parseError(res: Response): Promise<string> {
  const body = (await res.json().catch(() => null)) as
    | { detail?: string; message?: string; error?: string }
    | null
  return body?.detail ?? body?.message ?? body?.error ?? `Erreur ${res.status}`
}

export interface ScreenerResponse {
  timeframe: string
  computed_at: number
  cache_age_seconds: number
  rows: ScreenerDecisionRow[]
}

export async function getScreener(timeframe = '1h', force = false): Promise<ScreenerResponse> {
  const params = new URLSearchParams({ timeframe })
  if (force) params.set('force', 'true')
  appendEngineThresholds(params, await loadEngineThresholds())
  const res = await fetch(`/api/engine/screener?${params}`, { credentials: 'include' })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<ScreenerResponse>
}

export async function getScreenerDecisions(
  timeframe = '1h',
  force = false,
): Promise<ScreenerDecisionRow[]> {
  return (await getScreener(timeframe, force)).rows
}

export async function getDecisionDetail(
  symbol: string,
  timeframe = '1h',
  persist = true,
  includeCandles = false,
): Promise<DecisionDetail & { candles?: EngineCandle[]; provider?: string }> {
  const params = new URLSearchParams({
    timeframe,
    persist: persist ? 'true' : 'false',
  })
  if (includeCandles) params.set('include_candles', 'true')
  appendEngineThresholds(params, await loadEngineThresholds())
  const res = await fetch(
    `/api/engine/decisions/${encodeURIComponent(symbol)}?${params}`,
    { credentials: 'include' },
  )
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<DecisionDetail & { candles?: EngineCandle[]; provider?: string }>
}

interface EngineCandle {
  time: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}
