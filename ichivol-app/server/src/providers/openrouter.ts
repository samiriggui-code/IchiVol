import type { LlmProvider } from './types.js'
import { createOpenAiCompatibleProvider } from './openaiCompatible.js'

export interface OpenRouterProviderOptions {
  apiKey: string | undefined
  model: string
}

export function createOpenRouterProvider(opts: OpenRouterProviderOptions): LlmProvider {
  return createOpenAiCompatibleProvider({
    name: 'openrouter',
    baseUrl: 'https://openrouter.ai/api/v1',
    apiKey: opts.apiKey,
    model: opts.model,
    extraHeaders: {
      'HTTP-Referer': 'http://localhost:5173',
      'X-Title': 'IchiVol',
    },
  })
}
