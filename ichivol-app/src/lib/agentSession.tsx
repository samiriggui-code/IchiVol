import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
} from 'react'
import type {
  AgentChatResponse,
  AgentCitation,
  AgentDecisionPayload,
  AgentLivePayload,
  AgentMode,
} from './agent'
import {
  defaultPromptFor,
  type CopilotLaunchKind,
} from './copilotPrompts'

export interface CopilotLaunch {
  /** Incrémenté à chaque launch — AgentPanel s’en sert pour auto-send. */
  requestId: number
  mode: AgentMode
  prompt: string
  /** Si true, envoie tout de suite ; sinon préremplit l’input. */
  autoSend: boolean
  decision: AgentDecisionPayload | null
  live: AgentLivePayload | null
  kind: CopilotLaunchKind
}

export interface ChatEntry {
  role: 'user' | 'assistant'
  content: string
  citations?: AgentCitation[]
  disclaimer?: string
  pendingAction?: AgentChatResponse['pendingAction']
}

interface AgentSessionContextValue {
  /** Bulle legacy — préférer /app/agent via useCopilotNav. */
  open: boolean
  setOpen: (open: boolean) => void
  decisionPayload: AgentDecisionPayload | null
  /** @deprecated préférer useCopilotNav().explainDecision */
  openWithDecision: (decision: AgentDecisionPayload) => void
  clearDecision: () => void
  decisionRequestId: number
  launch: CopilotLaunch | null
  /** Enfile un intent Copilot (la navigation est dans useCopilotNav). */
  queueLaunch: (opts: {
    kind: CopilotLaunchKind
    decision?: AgentDecisionPayload | null
    live?: AgentLivePayload | null
    topic?: string
    symbol?: string
    autoSend?: boolean
    promptOverride?: string
  }) => void
  clearLaunch: () => void
  /** True si ce requestId n’a pas encore été consommé (évite double-send au remount). */
  takeLaunch: (requestId: number) => boolean
  threadId: string | null
  setThreadId: (id: string | null) => void
  assumedSymbol: string | null
  assumedTimeframe: string | null
  setAssumedSlots: (symbol: string | null, timeframe: string | null) => void
  /** Conversation — survit à la navigation dans le dashboard. */
  mode: AgentMode
  setMode: (mode: AgentMode) => void
  input: string
  setInput: (value: string) => void
  history: ChatEntry[]
  setHistory: Dispatch<SetStateAction<ChatEntry[]>>
  loading: boolean
  setLoading: (loading: boolean) => void
  /** Incrémenté à chaque nouveau tour — ignore les réponses périmées. */
  bumpChatGeneration: () => number
  getChatGeneration: () => number
  actionBusy: boolean
  setActionBusy: (busy: boolean) => void
  error: string | null
  setError: (error: string | null) => void
  clearChat: () => void
}

const AgentSessionContext = createContext<AgentSessionContextValue | null>(null)

export function AgentSessionProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const [decisionPayload, setDecisionPayload] = useState<AgentDecisionPayload | null>(null)
  const [decisionRequestId, setDecisionRequestId] = useState(0)
  const [launch, setLaunch] = useState<CopilotLaunch | null>(null)
  const [threadId, setThreadId] = useState<string | null>(null)
  const [assumedSymbol, setAssumedSymbol] = useState<string | null>(null)
  const [assumedTimeframe, setAssumedTimeframe] = useState<string | null>(null)
  const [mode, setMode] = useState<AgentMode>('research')
  const [input, setInput] = useState('')
  const [history, setHistory] = useState<ChatEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [actionBusy, setActionBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const lastLaunchId = useRef(0)
  const chatGeneration = useRef(0)

  const setAssumedSlots = useCallback((symbol: string | null, timeframe: string | null) => {
    setAssumedSymbol(symbol)
    setAssumedTimeframe(timeframe)
  }, [])

  const bumpChatGeneration = useCallback(() => {
    chatGeneration.current += 1
    return chatGeneration.current
  }, [])

  const getChatGeneration = useCallback(() => chatGeneration.current, [])

  const clearChat = useCallback(() => {
    chatGeneration.current += 1
    setHistory([])
    setInput('')
    setError(null)
    setLoading(false)
    setActionBusy(false)
  }, [])

  const takeLaunch = useCallback((requestId: number) => {
    if (requestId === lastLaunchId.current) return false
    lastLaunchId.current = requestId
    return true
  }, [])

  const queueLaunch = useCallback(
    (opts: {
      kind: CopilotLaunchKind
      decision?: AgentDecisionPayload | null
      live?: AgentLivePayload | null
      topic?: string
      symbol?: string
      autoSend?: boolean
      promptOverride?: string
    }) => {
      const { mode: nextMode, prompt } = defaultPromptFor(opts.kind, {
        decision: opts.decision,
        live: opts.live,
        topic: opts.topic,
        symbol: opts.symbol ?? opts.decision?.symbol,
      })
      const decision = opts.decision ?? null
      const live = opts.live ?? null
      chatGeneration.current += 1
      setDecisionPayload(decision)
      setThreadId(null)
      setHistory([])
      setInput('')
      setError(null)
      setLoading(false)
      setMode(nextMode)
      if (decision) {
        setAssumedSymbol(decision.symbol)
        setAssumedTimeframe(decision.timeframe)
      } else if (live) {
        setAssumedSymbol(live.symbol)
        setAssumedTimeframe(live.interval)
      } else if (opts.symbol) {
        setAssumedSymbol(opts.symbol)
      }
      setDecisionRequestId((n) => n + 1)
      setLaunch({
        requestId: Date.now(),
        mode: nextMode,
        prompt: opts.promptOverride?.trim() || prompt,
        autoSend: opts.autoSend !== false,
        decision,
        live,
        kind: opts.kind,
      })
    },
    [],
  )

  const openWithDecision = useCallback(
    (decision: AgentDecisionPayload) => {
      queueLaunch({ kind: 'explain_decision', decision, autoSend: true })
      setOpen(true)
    },
    [queueLaunch],
  )

  const clearDecision = useCallback(() => {
    setDecisionPayload(null)
  }, [])

  const clearLaunch = useCallback(() => {
    setLaunch(null)
  }, [])

  const value = useMemo(
    () => ({
      open,
      setOpen,
      decisionPayload,
      openWithDecision,
      clearDecision,
      decisionRequestId,
      launch,
      queueLaunch,
      clearLaunch,
      takeLaunch,
      threadId,
      setThreadId,
      assumedSymbol,
      assumedTimeframe,
      setAssumedSlots,
      mode,
      setMode,
      input,
      setInput,
      history,
      setHistory,
      loading,
      setLoading,
      bumpChatGeneration,
      getChatGeneration,
      actionBusy,
      setActionBusy,
      error,
      setError,
      clearChat,
    }),
    [
      open,
      decisionPayload,
      openWithDecision,
      clearDecision,
      decisionRequestId,
      launch,
      queueLaunch,
      clearLaunch,
      takeLaunch,
      threadId,
      assumedSymbol,
      assumedTimeframe,
      setAssumedSlots,
      mode,
      input,
      history,
      loading,
      bumpChatGeneration,
      getChatGeneration,
      actionBusy,
      error,
      clearChat,
    ],
  )

  return <AgentSessionContext.Provider value={value}>{children}</AgentSessionContext.Provider>
}

export function useAgentSession(): AgentSessionContextValue {
  const ctx = useContext(AgentSessionContext)
  if (!ctx) throw new Error('useAgentSession must be used within AgentSessionProvider')
  return ctx
}
