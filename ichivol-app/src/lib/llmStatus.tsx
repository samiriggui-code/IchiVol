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

/** System One probe (jevos-v4 local ou TypeSafe hosted). */
export type JevConnState =
  | 'idle'
  | 'checking'
  | 'ok'
  | 'no_key'
  | 'unreachable'
  | 'error'
  | 'disabled'

export type JevProbeId = 'jevos' | 'typesafe'

export type JevProbeStatus = {
  id: JevProbeId
  state: JevConnState
  label: string
  provider?: string
  baseUrl?: string
  message?: string
  latencyMs?: number
  keyPresent?: boolean
  shadowEnabled?: boolean
}

export interface LlmStatusValue {
  state: LlmConnState
  provider?: LlmProvider
  model?: string
  message?: string
  latencyMs?: number
  checkedAt?: number
  /** Chat / Copilot LLM */
  chat: { state: LlmConnState; provider?: LlmProvider; model?: string; message?: string }
  /** jevos-v4 (System One local) */
  jevos: JevProbeStatus
  /** TypeSafe JEV hosted */
  typesafe: JevProbeStatus
  refresh: (opts?: { provider?: LlmProvider; model?: string; apiKey?: string }) => Promise<LlmTestResult | null>
}

const LlmStatusContext = createContext<LlmStatusValue | null>(null)

function emptyJev(id: JevProbeId): JevProbeStatus {
  return {
    id,
    state: 'idle',
    // Labels UI génériques — jamais de marque / provider / URL.
    label: id === 'jevos' ? 'Local' : 'Cloud',
  }
}

type HealthPayload = {
  shadow_enabled?: boolean
  configured_provider?: string
  base_url?: string
  key_present?: boolean
  probe?: {
    ok?: boolean
    error?: string
    latency_ms?: number
    provider?: string
    note?: string
  }
}

function publicJevMessage(state: JevConnState): string {
  switch (state) {
    case 'ok':
      return 'joignable'
    case 'no_key':
      return 'non configuré'
    case 'unreachable':
      return 'injoignable'
    case 'error':
      return 'erreur'
    case 'checking':
      return 'test…'
    case 'disabled':
      return 'off'
    case 'idle':
      return '…'
    default: {
      const _exhaustive: never = state
      return _exhaustive
    }
  }
}

async function probeJev(provider: JevProbeId): Promise<JevProbeStatus> {
  const label = provider === 'jevos' ? 'Local' : 'Cloud'
  try {
    const res = await fetch(`/api/engine/jev-shadow/health?provider=${provider}`, {
      credentials: 'include',
    })
    if (!res.ok) {
      const state: JevConnState = res.status === 422 ? 'error' : 'unreachable'
      return {
        id: provider,
        state,
        label,
        message: publicJevMessage(state),
      }
    }
    const data = (await res.json()) as HealthPayload
    const err = data.probe?.error
    if (!data.key_present || err === 'jev_key_missing') {
      return {
        id: provider,
        state: 'no_key',
        label,
        keyPresent: false,
        shadowEnabled: data.shadow_enabled,
        message: publicJevMessage('no_key'),
        latencyMs: data.probe?.latency_ms,
      }
    }
    if (data.probe?.ok) {
      return {
        id: provider,
        state: 'ok',
        label,
        keyPresent: true,
        shadowEnabled: data.shadow_enabled,
        message: publicJevMessage('ok'),
        latencyMs: data.probe.latency_ms,
      }
    }
    return {
      id: provider,
      state: 'unreachable',
      label,
      keyPresent: true,
      shadowEnabled: data.shadow_enabled,
      message: publicJevMessage('unreachable'),
      latencyMs: data.probe?.latency_ms,
    }
  } catch {
    return {
      id: provider,
      state: 'unreachable',
      label,
      message: publicJevMessage('unreachable'),
    }
  }
}

export function LlmStatusProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<LlmConnState>('idle')
  const [provider, setProvider] = useState<LlmProvider | undefined>()
  const [model, setModel] = useState<string | undefined>()
  const [message, setMessage] = useState<string | undefined>()
  const [latencyMs, setLatencyMs] = useState<number | undefined>()
  const [checkedAt, setCheckedAt] = useState<number | undefined>()
  const [jevos, setJevos] = useState<JevProbeStatus>(() => emptyJev('jevos'))
  const [typesafe, setTypesafe] = useState<JevProbeStatus>(() => emptyJev('typesafe'))

  const refresh = useCallback(async (opts?: {
    provider?: LlmProvider
    model?: string
    apiKey?: string
  }) => {
    setState('checking')
    setJevos((prev) => ({ ...prev, state: 'checking' }))
    setTypesafe((prev) => ({ ...prev, state: 'checking' }))

    const jevPromise = Promise.all([probeJev('jevos'), probeJev('typesafe')]).then(
      ([j, t]) => {
        setJevos(j)
        setTypesafe(t)
      },
    )

    let chatResult: LlmTestResult | null = null
    try {
      const result = await testLlm(opts ?? {})
      setState(result.status)
      setProvider(result.provider)
      setModel(result.model)
      setMessage(result.message)
      setLatencyMs(result.latencyMs)
      setCheckedAt(Date.now())
      chatResult = result
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Test LLM impossible'
      setState('unreachable')
      setMessage(msg)
      setCheckedAt(Date.now())
      chatResult = null
    }

    await jevPromise.catch(() => {
      setJevos((prev) =>
        prev.state === 'checking'
          ? { ...prev, state: 'unreachable', message: 'probe failed' }
          : prev,
      )
      setTypesafe((prev) =>
        prev.state === 'checking'
          ? { ...prev, state: 'unreachable', message: 'probe failed' }
          : prev,
      )
    })

    return chatResult
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const value = useMemo<LlmStatusValue>(
    () => ({
      state,
      provider,
      model,
      message,
      latencyMs,
      checkedAt,
      chat: { state, provider, model, message },
      jevos,
      typesafe,
      refresh,
    }),
    [state, provider, model, message, latencyMs, checkedAt, jevos, typesafe, refresh],
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
      return 'Copilot…'
    case 'checking':
      return 'Copilot…'
    case 'ok':
      return 'Copilot OK'
    case 'no_key':
      return 'Copilot : non configuré'
    case 'bad_key':
      return 'Copilot : config invalide'
    case 'unreachable':
      return 'Copilot injoignable'
    case 'error':
      return 'Copilot erreur'
    default: {
      const _exhaustive: never = state
      return _exhaustive
    }
  }
}

export function jevStatusLabel(probe: JevProbeStatus): string {
  switch (probe.state) {
    case 'idle':
      return `${probe.label}…`
    case 'checking':
      return `${probe.label}…`
    case 'ok':
      return `${probe.label} OK`
    case 'no_key':
      return `${probe.label} : clé`
    case 'unreachable':
      return `${probe.label} down`
    case 'error':
      return `${probe.label} err`
    case 'disabled':
      return `${probe.label} off`
    default: {
      const _exhaustive: never = probe.state
      return _exhaustive
    }
  }
}

/** Aggregate badge tone: worst of chat + System One probes. */
export function aggregateAiBadgeState(
  chat: LlmConnState,
  jevos: JevConnState,
  typesafe: JevConnState,
): LlmConnState {
  if (chat === 'checking' || jevos === 'checking' || typesafe === 'checking') return 'checking'
  if (chat === 'ok' || jevos === 'ok' || typesafe === 'ok') {
    if (
      chat === 'bad_key' ||
      chat === 'no_key' ||
      (chat !== 'ok' && chat !== 'idle' && chat !== 'checking')
    ) {
      // At least one System One up, chat struggling — still show mixed via 'ok' border with detail in title
      if (jevos === 'ok' || typesafe === 'ok') return 'ok'
    }
    if (chat === 'ok') return 'ok'
    if (jevos === 'ok' || typesafe === 'ok') return 'ok'
  }
  if (chat === 'no_key' || chat === 'bad_key') return chat
  if (chat === 'unreachable' || chat === 'error') return chat
  if (jevos === 'no_key' && typesafe === 'no_key' && chat === 'idle') return 'no_key'
  if (jevos === 'unreachable' || typesafe === 'unreachable') return 'unreachable'
  return chat === 'idle' ? 'idle' : chat
}
