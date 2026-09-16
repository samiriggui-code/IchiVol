import type { LlmProvider } from './types.js'
import { createOpenAiCompatibleProvider } from './openaiCompatible.js'

export interface OpenAiProviderOptions {
  apiKey: string | undefined
  model: string
}

export function createOpenAiProvider(opts: OpenAiProviderOptions): LlmProvider {
  return createOpenAiCompatibleProvider({
    name: 'openai',
    baseUrl: 'https://api.openai.com/v1',
    apiKey: opts.apiKey,
    model: opts.model,
  })
}
