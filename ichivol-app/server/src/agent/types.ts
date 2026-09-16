export type AgentMode = 'explain_signal' | 'research' | 'trade_idea' | 'explain_decision'

export interface LiveContextPayload {
  symbol: string
  interval: string
  price: number | null
  bias: 'bull' | 'bear' | 'neutral'
  rvol: number
  lastSignal: { kind: string; price: number; rvol: number; time: number } | null
}

export interface ScreenerRowPayload {
  symbol: string
  bias: string
  rvol: number
  lastSignal: string | null
  change24h: number
}

export interface DecisionStagePayload {
  id: string
  status: string
  summary: string
  codes?: string[]
}

/** Snapshot Decision Engine injecté (chiffres vérifiés côté client puis reformatés serveur). */
export interface DecisionContextPayload {
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
  stages: DecisionStagePayload[]
}

export interface AgentChatRequest {
  mode: AgentMode
  question: string
  live?: LiveContextPayload
  screenerRows?: ScreenerRowPayload[]
  decision?: DecisionContextPayload
  /** Hints pour tools serveur si le pack client est absent (E2). */
  symbol?: string
  timeframe?: string
  /** Thread persisté (E4) — créé si absent. */
  threadId?: string
  history?: Array<{ role: 'user' | 'assistant'; content: string }>
  provider?: 'anthropic' | 'openai' | 'openrouter'
}

export interface Citation {
  id: string
  title: string
  url: string
  kind: 'kb' | 'live-api'
}

export interface AgentChatResponse {
  answer: string
  disclaimer?: string
  citations: Citation[]
  provider: string
  model: string
  /** Intent résolu (E3). */
  intent?: string
  /** Thread persisté (E4). */
  threadId?: string
  assumedSymbol?: string | null
  assumedTimeframe?: string | null
  /** Action mute proposée — UI confirmera en E5. */
  pendingAction?: {
    intent: 'save_decision' | 'pin_symbol' | 'open_paper_position'
    symbol?: string
    timeframe?: string
    actionId?: string
  }
}
