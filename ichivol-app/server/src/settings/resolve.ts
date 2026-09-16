import type { Setting } from '@prisma/client'
import { config, type ProviderName } from '../config.js'
import { db } from '../db.js'
import { decryptSecret } from './secrets.js'
import type { SettingsPublic } from './types.js'

const DEFAULT_ICHIMOKU = { tenkan: 9, kijun: 26, senkouB: 52, displacement: 26 }
const DEFAULT_VOLUME = {
  rvolLen: 20,
  rvolConfirm: 1.5,
  spikeMult: 2,
  rvolLow: 0.7,
  rvolSignificant: 1.5,
  rvolStrong: 2.0,
  rvolAnomaly: 3.0,
  atrDeadPercentile: 0.15,
  atrExtremePercentile: 0.9,
  atrStopMultiplier: 1.5,
}

function asProvider(value: string | undefined): ProviderName {
  if (value === 'openai' || value === 'openrouter' || value === 'anthropic') return value
  return config.llmProvider
}

function envKeyFor(provider: ProviderName): string | undefined {
  switch (provider) {
    case 'openai':
      return config.openaiApiKey
    case 'openrouter':
      return config.openrouterApiKey
    case 'anthropic':
      return config.anthropicApiKey
    default: {
      const _exhaustive: never = provider
      return _exhaustive
    }
  }
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return ['binance']
  return value.filter((v): v is string => typeof v === 'string')
}

function asNumberRecord(value: unknown, fallback: Record<string, number>): Record<string, number> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return fallback
  const out: Record<string, number> = { ...fallback }
  for (const [k, v] of Object.entries(value)) {
    if (typeof v === 'number' && Number.isFinite(v)) out[k] = v
  }
  return out
}

export async function getOrCreateSetting(userId: string): Promise<Setting> {
  const existing = await db.setting.findUnique({ where: { userId } })
  if (existing) return existing
  return db.setting.create({
    data: {
      userId,
      llmProvider: config.llmProvider,
      llmModel: config.llmModel,
    },
  })
}

export function toPublicSettings(row: Setting): SettingsPublic {
  const llmProvider = asProvider(row.llmProvider)
  const llmApiKeySet = Boolean(row.llmApiKeyEnc)
  const llmReady = llmApiKeySet || Boolean(envKeyFor(llmProvider))
  const llmModel = row.llmModel || config.llmModel

  const providers: ProviderName[] = ['openrouter', 'anthropic', 'openai']
  const llmConnections = providers.map((p) => {
    const ui = p === llmProvider && llmApiKeySet
    const env = Boolean(envKeyFor(p))
    let keySource: 'ui' | 'env' | 'both' | 'none' = 'none'
    if (ui && env) keySource = 'both'
    else if (ui) keySource = 'ui'
    else if (env) keySource = 'env'
    return {
      provider: p,
      connected: ui || env,
      keySource,
      active: p === llmProvider,
      model: p === llmProvider ? llmModel : null,
    }
  })

  return {
    activeSources: asStringArray(row.activeSources),
    ichimokuParams: asNumberRecord(row.ichimokuParams, DEFAULT_ICHIMOKU),
    volumeParams: asNumberRecord(row.volumeParams, DEFAULT_VOLUME),
    theme: row.theme || 'dark',
    llmProvider,
    llmModel,
    llmApiKeySet,
    llmReady,
    llmConnections,
    twelveDataApiKeySet: Boolean(row.twelveDataApiKeyEnc),
  }
}

/** The user's own Twelve Data key, decrypted -- or `undefined` if they
 * haven't set one, in which case the engine falls back to its own
 * operator-wide `TWELVE_DATA_API_KEY` (engine/.env) unchanged. */
export async function resolveTwelveDataKeyForUser(userId: string): Promise<string | undefined> {
  const row = await getOrCreateSetting(userId)
  return row.twelveDataApiKeyEnc ? decryptSecret(row.twelveDataApiKeyEnc) : undefined
}

export interface ResolvedLlm {
  provider: ProviderName
  model: string
  apiKey: string | undefined
}

export async function resolveLlmForUser(userId: string): Promise<ResolvedLlm> {
  const row = await getOrCreateSetting(userId)
  const provider = asProvider(row.llmProvider)
  const model = row.llmModel || config.llmModel
  if (row.llmApiKeyEnc) {
    return { provider, model, apiKey: decryptSecret(row.llmApiKeyEnc) }
  }
  return { provider, model, apiKey: envKeyFor(provider) }
}
