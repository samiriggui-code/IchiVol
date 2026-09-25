import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import {
  testLlm,
  type LlmProvider,
  type LlmTestResult,
  type LlmTestStatus,
} from './settings'

export type LlmConnState = 'idle' | 'checking' | LlmTestStatus

export interface LlmStatusValue {
  state: LlmConnState
  provider?: LlmProvider
  model?: string
  message?: string
  latencyMs?: number
  checkedAt?: number
  refresh: (opts?: { provider?: LlmProvider; model?: string; apiKey?: string }) => Promise<LlmTestResult | null>
}

const LlmStatusContext = createContext<LlmStatusValue | null>(null)

export function LlmStatusProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<LlmConnState>('idle')
  const [provider, setProvider] = useState<LlmProvider | undefined>()
  const [model, setModel] = useState<string | undefined>()
  const [message, setMessage] = useState<string | undefined>()
  const [latencyMs, setLatencyMs] = useState<number | undefined>()
  const [checkedAt, setCheckedAt] = useState<number | undefined>()

  const refresh = useCallback(async (opts?: {
    provider?: LlmProvider
    model?: string
    apiKey?: string
  }) => {
    setState('checking')
    try {
      const result = await testLlm(opts ?? {})
      setState(result.status)
      setProvider(result.provider)
      setModel(result.model)
      setMessage(result.message)
      setLatencyMs(result.latencyMs)
      setCheckedAt(Date.now())
      return result
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Test LLM impossible'
      setState('unreachable')
      setMessage(msg)
      setCheckedAt(Date.now())
      return null
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const value = useMemo<LlmStatusValue>(
    () => ({ state, provider, model, message, latencyMs, checkedAt, refresh }),
    [state, provider, model, message, latencyMs, checkedAt, refresh],
  )

  return <LlmStatusContext.Provider value={value}>{children}</LlmStatusContext.Provider>
}

export function useLlmStatus(): LlmStatusValue {
  const ctx = useContext(LlmStatusContext)
  if (!ctx) throw new Error('useLlmStatus hors LlmStatusProvider')
  return ctx
}

export function llmStatusLabel(state: LlmConnState): string {
  switch (state) {
    case 'idle':
      return 'LLM…'
    case 'checking':
      return 'LLM test…'
    case 'ok':
      return 'LLM connecté'
    case 'no_key':
      return 'LLM : clé manquante'
    case 'bad_key':
      return 'LLM : clé invalide'
    case 'unreachable':
      return 'LLM injoignable'
    case 'error':
      return 'LLM erreur'
    default: {
      const _exhaustive: never = state
      return _exhaustive
    }
  }
}
