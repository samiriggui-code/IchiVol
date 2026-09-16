import type { DecisionDetail } from './decisions'

export type AgentMode = 'explain_signal' | 'research' | 'trade_idea' | 'explain_decision'

export interface AgentLivePayload {
  symbol: string
  interval: string
  price: number | null
  bias: 'bull' | 'bear' | 'neutral'
  rvol: number
  lastSignal: { kind: string; price: number; rvol: number; time: number } | null
}

export interface AgentScreenerRowPayload {
  symbol: string
  bias: string
  rvol: number
  lastSignal: string | null
  change24h: number
}

export interface AgentDecisionStagePayload {
  id: string
  status: string
  summary: string
  codes?: string[]
}

export interface AgentDecisionPayload {
  symbol: string
  timeframe: string
  price?: number | null
  combiner: string
  direction: string
  gateDecision?: string | null
  confidence?: number | null
  rvol?: number | null
  reasons?: string[]
  risks?: string[]
  invalidation?: string[]
  stages: AgentDecisionStagePayload[]
}

export interface AgentChatRequest {
  mode: AgentMode
  question: string
  live?: AgentLivePayload
  screenerRows?: AgentScreenerRowPayload[]
  decision?: AgentDecisionPayload
  symbol?: string
  timeframe?: string
  threadId?: string
  history?: Array<{ role: 'user' | 'assistant'; content: string }>
}

export interface AgentCitation {
  id: string
  title: string
  url: string
  kind: 'kb' | 'live-api'
}

export interface AgentChatResponse {
  answer: string
  disclaimer?: string
  citations: AgentCitation[]
  provider: string
  model: string
  intent?: string
  threadId?: string
  assumedSymbol?: string | null
  assumedTimeframe?: string | null
  pendingAction?: {
    intent: 'save_decision' | 'pin_symbol' | 'open_paper_position'
    symbol?: string
    timeframe?: string
    actionId?: string
  }
}

export function decisionPayloadFromDetail(detail: DecisionDetail): AgentDecisionPayload {
  const gate =
    typeof detail.pipeline?.decision === 'string' ? detail.pipeline.decision : null
  return {
    symbol: detail.symbol,
    timeframe: detail.timeframe,
    price: detail.price,
    combiner: detail.decision,
    direction: detail.direction,
    gateDecision: gate,
    confidence: detail.confidence,
    rvol: detail.rvol,
    reasons: detail.reasons,
    risks: detail.risks,
    invalidation: detail.invalidation,
    stages: (detail.pipeline?.stages ?? []).map((s) => ({
      id: s.id,
      status: s.status,
      summary: s.summary,
      codes: s.codes,
    })),
  }
}

export async function askAgent(payload: AgentChatRequest): Promise<AgentChatResponse> {
  const res = await fetch('/api/agent/chat', {
    method: 'POST',
    credentials: 'include',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { error?: string } | null
    throw new Error(body?.error ?? `Agent ${res.status}`)
  }
  return res.json() as Promise<AgentChatResponse>
}

export async function confirmAgentAction(payload: {
  intent: 'save_decision' | 'pin_symbol' | 'open_paper_position'
  confirm: boolean
  symbol?: string
  timeframe?: string
  threadId?: string
  actionId?: string
}): Promise<{
  ok: boolean
  status: string
  message?: string
  error?: string
  result?: Record<string, unknown>
}> {
  const res = await fetch('/api/agent/actions/confirm', {
    method: 'POST',
    credentials: 'include',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  })
  const body = (await res.json().catch(() => null)) as {
    ok?: boolean
    status?: string
    message?: string
    error?: string
    result?: Record<string, unknown>
  } | null
  if (!res.ok) {
    throw new Error(body?.error ?? `Action ${res.status}`)
  }
  return {
    ok: Boolean(body?.ok),
    status: body?.status ?? 'unknown',
    message: body?.message,
    result: body?.result,
  }
}
