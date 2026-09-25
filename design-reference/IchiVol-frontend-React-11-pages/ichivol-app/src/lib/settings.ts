export type LlmProvider = 'anthropic' | 'openai' | 'openrouter'

export type LlmTestStatus = 'ok' | 'no_key' | 'bad_key' | 'unreachable' | 'error'

export interface LlmModelOption {
  id: string
  label: string
}

export const LLM_MODEL_CATALOG: Record<LlmProvider, LlmModelOption[]> = {
  anthropic: [
    { id: 'claude-sonnet-4-5', label: 'Claude Sonnet 4.5' },
    { id: 'claude-opus-4-5', label: 'Claude Opus 4.5' },
    { id: 'claude-haiku-4-5', label: 'Claude Haiku 4.5' },
    { id: 'claude-3-5-sonnet-20241022', label: 'Claude 3.5 Sonnet (Oct 2024)' },
    { id: 'claude-3-5-haiku-20241022', label: 'Claude 3.5 Haiku (Oct 2024)' },
  ],
  openai: [
    { id: 'gpt-4o', label: 'GPT-4o' },
    { id: 'gpt-4o-mini', label: 'GPT-4o mini' },
    { id: 'gpt-4.1', label: 'GPT-4.1' },
    { id: 'gpt-4.1-mini', label: 'GPT-4.1 mini' },
    { id: 'o4-mini', label: 'o4-mini' },
  ],
  openrouter: [
    { id: 'openai/gpt-4o-mini', label: 'OpenAI · GPT-4o mini' },
    { id: 'openai/gpt-4o', label: 'OpenAI · GPT-4o' },
    { id: 'anthropic/claude-sonnet-4.5', label: 'Anthropic · Claude Sonnet 4.5' },
    { id: 'anthropic/claude-3.5-sonnet', label: 'Anthropic · Claude 3.5 Sonnet' },
    { id: 'google/gemini-2.5-flash', label: 'Google · Gemini 2.5 Flash' },
    { id: 'deepseek/deepseek-chat', label: 'DeepSeek · Chat' },
  ],
}

export const DEFAULT_MODELS: Record<LlmProvider, string> = {
  anthropic: 'claude-sonnet-4-5',
  openai: 'gpt-4o-mini',
  openrouter: 'openai/gpt-4o-mini',
}

export interface LlmConnection {
  provider: LlmProvider
  connected: boolean
  keySource: 'ui' | 'env' | 'both' | 'none'
  active: boolean
  model: string | null
}

export interface AppSettings {
  activeSources: string[]
  ichimokuParams: {
    tenkan: number
    kijun: number
    senkouB: number
    displacement: number
  }
  volumeParams: {
    rvolLen: number
    rvolConfirm: number
    spikeMult: number
    rvolLow: number
    rvolSignificant: number
    rvolStrong: number
    rvolAnomaly: number
    atrDeadPercentile: number
    atrExtremePercentile: number
    atrStopMultiplier: number
  }
  theme: 'dark' | 'light' | string
  llmProvider: LlmProvider
  llmModel: string
  llmApiKeySet: boolean
  llmReady: boolean
  llmConnections?: LlmConnection[]
  llmModels?: Record<LlmProvider, LlmModelOption[]>
  twelveDataApiKeySet: boolean
  pushAlertPrefs?: {
    enabled: boolean
    targetStop: boolean
    accel: boolean
    directionFlip: boolean
    nearPct: number
    cooldownMin: number
  }
}

export interface SettingsPatch {
  activeSources?: string[]
  ichimokuParams?: AppSettings['ichimokuParams']
  volumeParams?: AppSettings['volumeParams']
  theme?: string
  llmProvider?: LlmProvider
  llmModel?: string
  /** omit = keep; "" = clear; non-empty = set */
  llmApiKey?: string
  /** omit = keep; "" = clear; non-empty = set. Overrides the operator's
   * Twelve Data key for AAPL/TSLA requests only -- forex/metal/index/energy
   * are already free via biquote, see docs/MARKET-DATA-STRATEGY.md. */
  twelveDataApiKey?: string
  pushAlertPrefs?: Partial<NonNullable<AppSettings['pushAlertPrefs']>>
}

export interface LlmTestResult {
  ok: boolean
  status: LlmTestStatus
  provider: LlmProvider
  model: string
  latencyMs: number
  message: string
}

export interface LlmTestRequest {
  provider?: LlmProvider
  model?: string
  apiKey?: string
}

async function parseError(res: Response): Promise<string> {
  const body = (await res.json().catch(() => null)) as { error?: string; message?: string } | null
  return body?.error ?? body?.message ?? `Erreur ${res.status}`
}

export async function getSettings(): Promise<AppSettings> {
  const res = await fetch('/api/settings', { credentials: 'include' })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<AppSettings>
}

export async function patchSettings(patch: SettingsPatch): Promise<AppSettings> {
  const res = await fetch('/api/settings', {
    method: 'PATCH',
    credentials: 'include',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(patch),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<AppSettings>
}

export async function testLlm(payload: LlmTestRequest = {}): Promise<LlmTestResult> {
  const res = await fetch('/api/settings/llm-test', {
    method: 'POST',
    credentials: 'include',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  })
  const data = (await res.json().catch(() => null)) as LlmTestResult | { error?: string } | null
  if (data && 'status' in data && 'provider' in data) return data
  throw new Error(
    data && 'error' in data && data.error ? data.error : `Test LLM échoué (${res.status})`,
  )
}

export function modelsForProvider(
  provider: LlmProvider,
  catalog?: Record<LlmProvider, LlmModelOption[]>,
): LlmModelOption[] {
  return catalog?.[provider] ?? LLM_MODEL_CATALOG[provider]
}

export function resolveModelSelection(provider: LlmProvider, current: string): {
  selectValue: string
  custom: string
  isCustom: boolean
} {
  const known = LLM_MODEL_CATALOG[provider].some((m) => m.id === current)
  if (known) return { selectValue: current, custom: '', isCustom: false }
  if (!current) return { selectValue: DEFAULT_MODELS[provider], custom: '', isCustom: false }
  return { selectValue: '__custom__', custom: current, isCustom: true }
}
