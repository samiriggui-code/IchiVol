import type { LlmProvider } from '../../lib/settings'

export type SettingsSection =
  | 'market'
  | 'llm'
  | 'alerts'
  | 'risk'
  | 'connections'
  | 'environment'

export const SECTIONS: { id: SettingsSection; label: string; blurb: string }[] = [
  { id: 'market', label: 'Marché et univers', blurb: 'Indicateurs · univers (lecture)' },
  { id: 'llm', label: 'LLM', blurb: 'Provider, modèle, clé' },
  { id: 'alerts', label: 'Alertes', blurb: 'Push · préférences' },
  { id: 'risk', label: 'Limites de risque', blurb: 'Risk Kernel · lecture seule' },
  { id: 'connections', label: 'Connexions', blurb: 'Feeds · Twelve Data' },
  { id: 'environment', label: 'Environnement', blurb: 'PAPER · identité' },
]

export const SOURCES = [
  { id: 'binance', label: 'Binance Vision (data)' },
  { id: 'bybit', label: 'Bybit (data)' },
  { id: 'okx', label: 'OKX (data)' },
] as const

export const PROVIDERS: { id: LlmProvider; label: string; keyHint: string }[] = [
  { id: 'openrouter', label: 'OpenRouter', keyHint: 'sk-or-…' },
  { id: 'anthropic', label: 'Anthropic', keyHint: 'sk-ant-…' },
  { id: 'openai', label: 'OpenAI', keyHint: 'sk-…' },
]

export function providerLabel(id: LlmProvider): string {
  return PROVIDERS.find((p) => p.id === id)?.label ?? id
}
