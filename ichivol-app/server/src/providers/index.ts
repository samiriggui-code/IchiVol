import { config, type ProviderName } from '../config.js'
import { createAnthropicProvider } from './anthropic.js'
import { createOpenAiProvider } from './openai.js'
import { createOpenRouterProvider } from './openrouter.js'
import type { LlmProvider } from './types.js'

export interface ProviderOverrides {
  provider?: ProviderName
  apiKey?: string
  model?: string
}

export function getProvider(overrides?: ProviderOverrides | ProviderName): LlmProvider {
  const opts: ProviderOverrides =
    typeof overrides === 'string' ? { provider: overrides } : (overrides ?? {})
  const name = opts.provider ?? config.llmProvider
  const model = opts.model ?? config.llmModel
  const apiKey = opts.apiKey

  switch (name) {
    case 'openai':
      return createOpenAiProvider({ apiKey: apiKey ?? config.openaiApiKey, model })
    case 'openrouter':
      return createOpenRouterProvider({ apiKey: apiKey ?? config.openrouterApiKey, model })
    case 'anthropic':
      return createAnthropicProvider({ apiKey: apiKey ?? config.anthropicApiKey, model })
    default: {
      const _exhaustive: never = name
      return _exhaustive
    }
  }
}

export type { ChatMessage, LlmProvider, ProviderChatResult } from './types.js'
