import type { Request, Response } from 'express'
import { type ProviderName } from '../config.js'
import { db } from '../db.js'
import { testLlmConnection } from './llmTest.js'
import { DEFAULT_LLM_MODELS, LLM_MODEL_CATALOG } from './models.js'
import { getOrCreateSetting, resolveLlmForUser, toPublicSettings } from './resolve.js'
import { encryptSecret } from './secrets.js'
import type { SettingsPatch } from './types.js'

const PROVIDERS = new Set<ProviderName>(['anthropic', 'openai', 'openrouter'])
const SOURCES = new Set(['binance', 'bybit', 'okx'])

function isProvider(value: unknown): value is ProviderName {
  return typeof value === 'string' && PROVIDERS.has(value as ProviderName)
}

function parsePatch(body: unknown): { ok: true; data: SettingsPatch } | { ok: false; error: string } {
  if (!body || typeof body !== 'object' || Array.isArray(body)) {
    return { ok: false, error: 'Body JSON requis' }
  }
  const raw = body as Record<string, unknown>
  const data: SettingsPatch = {}

  if ('llmProvider' in raw) {
    if (!isProvider(raw.llmProvider)) return { ok: false, error: 'llmProvider invalide' }
    data.llmProvider = raw.llmProvider
  }
  if ('llmModel' in raw) {
    if (typeof raw.llmModel !== 'string' || !raw.llmModel.trim()) {
      return { ok: false, error: 'llmModel invalide' }
    }
    data.llmModel = raw.llmModel.trim()
  }
  if ('llmApiKey' in raw) {
    if (typeof raw.llmApiKey !== 'string') return { ok: false, error: 'llmApiKey invalide' }
    data.llmApiKey = raw.llmApiKey
  }
  if ('twelveDataApiKey' in raw) {
    if (typeof raw.twelveDataApiKey !== 'string') {
      return { ok: false, error: 'twelveDataApiKey invalide' }
    }
    data.twelveDataApiKey = raw.twelveDataApiKey
  }
  if ('theme' in raw) {
    if (raw.theme !== 'dark' && raw.theme !== 'light') return { ok: false, error: 'theme invalide' }
    data.theme = raw.theme
  }
  if ('activeSources' in raw) {
    if (!Array.isArray(raw.activeSources) || raw.activeSources.length === 0) {
      return { ok: false, error: 'activeSources invalide' }
    }
    const sources = raw.activeSources.filter((s): s is string => typeof s === 'string' && SOURCES.has(s))
    if (sources.length === 0) return { ok: false, error: 'activeSources: au moins une source valide' }
    data.activeSources = sources
  }
  if ('ichimokuParams' in raw) {
    if (!raw.ichimokuParams || typeof raw.ichimokuParams !== 'object') {
      return { ok: false, error: 'ichimokuParams invalide' }
    }
    data.ichimokuParams = raw.ichimokuParams as Record<string, number>
  }
  if ('volumeParams' in raw) {
    if (!raw.volumeParams || typeof raw.volumeParams !== 'object') {
      return { ok: false, error: 'volumeParams invalide' }
    }
    data.volumeParams = raw.volumeParams as Record<string, number>
  }

  return { ok: true, data }
}

export async function handleGetSettings(req: Request, res: Response): Promise<void> {
  if (!req.user) {
    res.status(401).json({ error: 'Non authentifié' })
    return
  }
  const row = await getOrCreateSetting(req.user.id)
  res.json({
    ...toPublicSettings(row),
    llmModels: LLM_MODEL_CATALOG,
  })
}

export async function handlePatchSettings(req: Request, res: Response): Promise<void> {
  if (!req.user) {
    res.status(401).json({ error: 'Non authentifié' })
    return
  }

  const parsed = parsePatch(req.body)
  if (!parsed.ok) {
    res.status(400).json({ error: parsed.error })
    return
  }

  await getOrCreateSetting(req.user.id)

  const update: {
    llmProvider?: string
    llmModel?: string
    llmApiKeyEnc?: string | null
    twelveDataApiKeyEnc?: string | null
    theme?: string
    activeSources?: string[]
    ichimokuParams?: Record<string, number>
    volumeParams?: Record<string, number>
  } = {}

  const { data } = parsed
  if (data.llmProvider !== undefined) update.llmProvider = data.llmProvider
  if (data.llmModel !== undefined) update.llmModel = data.llmModel
  if (data.theme !== undefined) update.theme = data.theme
  if (data.activeSources !== undefined) update.activeSources = data.activeSources
  if (data.ichimokuParams !== undefined) update.ichimokuParams = data.ichimokuParams
  if (data.volumeParams !== undefined) update.volumeParams = data.volumeParams

  if (data.llmApiKey !== undefined) {
    const trimmed = data.llmApiKey.trim()
    update.llmApiKeyEnc = trimmed ? encryptSecret(trimmed) : null
  }
  if (data.twelveDataApiKey !== undefined) {
    const trimmed = data.twelveDataApiKey.trim()
    update.twelveDataApiKeyEnc = trimmed ? encryptSecret(trimmed) : null
  }

  const row = await db.setting.update({
    where: { userId: req.user.id },
    data: update,
  })

  res.json({
    ...toPublicSettings(row),
    llmModels: LLM_MODEL_CATALOG,
  })
}

/** Test provider+model+clé (sauvegardés ou override body, sans persister la clé de test). */
export async function handleLlmTest(req: Request, res: Response): Promise<void> {
  if (!req.user) {
    res.status(401).json({ error: 'Non authentifié' })
    return
  }

  const body = (req.body ?? {}) as {
    provider?: unknown
    model?: unknown
    apiKey?: unknown
  }

  const resolved = await resolveLlmForUser(req.user.id)
  const provider = isProvider(body.provider) ? body.provider : resolved.provider
  const model =
    typeof body.model === 'string' && body.model.trim()
      ? body.model.trim()
      : resolved.model || DEFAULT_LLM_MODELS[provider]
  const apiKey =
    typeof body.apiKey === 'string' && body.apiKey.trim()
      ? body.apiKey.trim()
      : resolved.apiKey

  const result = await testLlmConnection({ provider, model, apiKey })
  res.status(result.ok ? 200 : 422).json(result)
}
