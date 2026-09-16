import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import type { AgentDecisionPayload } from './agent'

interface AgentSessionContextValue {
  open: boolean
  setOpen: (open: boolean) => void
  decisionPayload: AgentDecisionPayload | null
  /** Ouvre le chat et charge une décision à expliquer (auto-send au panel). */
  openWithDecision: (decision: AgentDecisionPayload) => void
  clearDecision: () => void
  /** Incrémenté à chaque openWithDecision pour forcer un re-send. */
  decisionRequestId: number
  /** Thread DB courant (E4). */
  threadId: string | null
  setThreadId: (id: string | null) => void
  assumedSymbol: string | null
  assumedTimeframe: string | null
  setAssumedSlots: (symbol: string | null, timeframe: string | null) => void
}

const AgentSessionContext = createContext<AgentSessionContextValue | null>(null)

export function AgentSessionProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const [decisionPayload, setDecisionPayload] = useState<AgentDecisionPayload | null>(null)
  const [decisionRequestId, setDecisionRequestId] = useState(0)
  const [threadId, setThreadId] = useState<string | null>(null)
  const [assumedSymbol, setAssumedSymbol] = useState<string | null>(null)
  const [assumedTimeframe, setAssumedTimeframe] = useState<string | null>(null)

  const setAssumedSlots = useCallback((symbol: string | null, timeframe: string | null) => {
    setAssumedSymbol(symbol)
    setAssumedTimeframe(timeframe)
  }, [])

  const openWithDecision = useCallback((decision: AgentDecisionPayload) => {
    setDecisionPayload(decision)
    setDecisionRequestId((n) => n + 1)
    setThreadId(null) // nouveau thread serveur au prochain chat
    setAssumedSymbol(decision.symbol)
    setAssumedTimeframe(decision.timeframe)
    setOpen(true)
  }, [])

  const clearDecision = useCallback(() => {
    setDecisionPayload(null)
  }, [])

  const value = useMemo(
    () => ({
      open,
      setOpen,
      decisionPayload,
      openWithDecision,
      clearDecision,
      decisionRequestId,
      threadId,
      setThreadId,
      assumedSymbol,
      assumedTimeframe,
      setAssumedSlots,
    }),
    [
      open,
      decisionPayload,
      openWithDecision,
      clearDecision,
      decisionRequestId,
      threadId,
      assumedSymbol,
      assumedTimeframe,
      setAssumedSlots,
    ],
  )

  return <AgentSessionContext.Provider value={value}>{children}</AgentSessionContext.Provider>
}

export function useAgentSession(): AgentSessionContextValue {
  const ctx = useContext(AgentSessionContext)
  if (!ctx) throw new Error('useAgentSession must be used within AgentSessionProvider')
  return ctx
}
