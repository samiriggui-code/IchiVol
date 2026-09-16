import type { ProviderName } from '../config.js'

export interface LlmModelOption {
  id: string
  label: string
}

/** Catalogues stables — le front et le test de connectivité partagent les mêmes IDs. */
export const LLM_MODEL_CATALOG: Record<ProviderName, LlmModelOption[]> = {
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

export const DEFAULT_LLM_MODELS: Record<ProviderName, string> = {
  anthropic: 'claude-sonnet-4-5',
  openai: 'gpt-4o-mini',
  openrouter: 'openai/gpt-4o-mini',
}

export function isKnownModel(provider: ProviderName, model: string): boolean {
  return LLM_MODEL_CATALOG[provider].some((m) => m.id === model)
}
