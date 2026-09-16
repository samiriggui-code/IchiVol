import type { ProviderName } from '../config.js'

export interface LlmConnectionPublic {
  provider: ProviderName
  /** Clé présente (UI et/ou .env). */
  connected: boolean
  /** ui | env | both | none */
  keySource: 'ui' | 'env' | 'both' | 'none'
  /** Provider actuellement sélectionné pour l’agent. */
  active: boolean
  model: string | null
}

export interface SettingsPublic {
  activeSources: string[]
  ichimokuParams: Record<string, number>
  volumeParams: Record<string, number>
  theme: string
  llmProvider: ProviderName
  llmModel: string
  llmApiKeySet: boolean
  llmReady: boolean
  /** Tous les providers avec statut de clé (pour la table Settings). */
  llmConnections: LlmConnectionPublic[]
  twelveDataApiKeySet: boolean
}

export interface SettingsPatch {
  activeSources?: string[]
  ichimokuParams?: Record<string, number>
  volumeParams?: Record<string, number>
  theme?: string
  llmProvider?: ProviderName
  llmModel?: string
  /** Omit = keep; "" = clear; non-empty = set */
  llmApiKey?: string
  /** Omit = keep; "" = clear; non-empty = set. Overrides the operator's
   * TWELVE_DATA_API_KEY (engine/.env) for this user's equity requests only
   * (AAPL/TSLA -- forex/metal/index/energy are free via biquote already). */
  twelveDataApiKey?: string
}
