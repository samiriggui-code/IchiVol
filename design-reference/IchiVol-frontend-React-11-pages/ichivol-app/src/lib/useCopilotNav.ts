import { useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import type { AgentDecisionPayload, AgentLivePayload } from './agent'
import { useAgentSession } from './agentSession'
import type { CopilotLaunchKind } from './copilotPrompts'

/**
 * Redirige vers /app/agent avec un intent + prompt prérempli (et auto-send par défaut).
 * Pas de bulle vide : l’utilisateur arrive avec une question métier déjà formulée.
 */
export function useCopilotNav() {
  const navigate = useNavigate()
  const { queueLaunch } = useAgentSession()

  const go = useCallback(
    (opts: {
      kind: CopilotLaunchKind
      decision?: AgentDecisionPayload | null
      live?: AgentLivePayload | null
      topic?: string
      symbol?: string
      autoSend?: boolean
      promptOverride?: string
    }) => {
      queueLaunch(opts)
      navigate('/app/agent')
    },
    [navigate, queueLaunch],
  )

  return {
    go,
    explainDecision: (decision: AgentDecisionPayload, autoSend = true) =>
      go({ kind: 'explain_decision', decision, autoSend }),
    compareGates: (decision: AgentDecisionPayload, autoSend = true) =>
      go({ kind: 'compare_gates', decision, autoSend }),
    explainSignal: (live: AgentLivePayload, autoSend = true) =>
      go({ kind: 'explain_signal', live, autoSend }),
    tradeIdea: (symbol?: string, autoSend = true) =>
      go({ kind: 'trade_idea', symbol, autoSend }),
    research: (topic: string, autoSend = false) =>
      go({ kind: 'research', topic, autoSend }),
  }
}
