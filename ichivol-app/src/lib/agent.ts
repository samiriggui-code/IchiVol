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
  /** Demande une réponse en flux SSE (agent Claude ; sinon le serveur répond en JSON). */
  stream?: boolean
}

export interface AgentCitation {
  id: string
  title: string
  url: string
  kind: 'kb' | 'live-api'
}

export interface AgentToolCall {
  name: string
  input: Record<string, unknown>
  ok: boolean
  ms: number
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
  /** Outils moteur appelés par Claude pour cette réponse. */
  toolCalls?: AgentToolCall[]
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

export interface AgentStreamHandlers {
  onText?: (delta: string) => void
  onToolStart?: (name: string) => void
  onToolEnd?: (name: string, ok: boolean, ms: number) => void
}

type AgentStreamEvent =
  | { type: 'text'; delta: string }
  | { type: 'tool_start'; name: string }
  | { type: 'tool_end'; name: string; ok: boolean; ms: number }
  | { type: 'done'; response: AgentChatResponse }
  | { type: 'error'; error: string }

/**
 * Comme `askAgent` mais lit le flux SSE : le texte arrive au fil de l'eau.
 * Si le serveur répond en JSON (autre fournisseur, action à confirmer), on
 * retombe sur la réponse classique — l'appelant n'a rien à distinguer.
 */
export async function askAgentStream(
  payload: AgentChatRequest,
  handlers: AgentStreamHandlers = {},
  signal?: AbortSignal,
): Promise<AgentChatResponse> {
  const res = await fetch('/api/agent/chat', {
    method: 'POST',
    credentials: 'include',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ ...payload, stream: true }),
    signal,
  })
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { error?: string } | null
    throw new Error(body?.error ?? `Agent ${res.status}`)
  }
  if (!res.headers.get('content-type')?.includes('text/event-stream') || !res.body) {
    return res.json() as Promise<AgentChatResponse>
  }

  let final: AgentChatResponse | null = null
  const handle = (raw: string) => {
    const line = raw.split('\n').find((l) => l.startsWith('data:'))
    if (!line) return
    const evt = JSON.parse(line.slice(5).trim()) as AgentStreamEvent
    if (evt.type === 'text') handlers.onText?.(evt.delta)
    else if (evt.type === 'tool_start') handlers.onToolStart?.(evt.name)
    else if (evt.type === 'tool_end') handlers.onToolEnd?.(evt.name, evt.ok, evt.ms)
    else if (evt.type === 'done') final = evt.response
    else if (evt.type === 'error') throw new Error(evt.error)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let sep: number
    while ((sep = buffer.indexOf('\n\n')) !== -1) {
      handle(buffer.slice(0, sep))
      buffer = buffer.slice(sep + 2)
    }
  }
  if (buffer.trim()) handle(buffer)
  if (!final) throw new Error('Flux interrompu avant la fin de la réponse')
  return final
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
