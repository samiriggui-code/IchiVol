/**
 * Clés LLM personnelles : une clé chiffrée PAR fournisseur (`llmKeysEnc`),
 * pour qu'en ajouter une (Anthropic) ne remplace jamais une autre (OpenRouter).
 *
 * L'ancienne colonne `llmApiKeyEnc` (une seule clé, rattachée au fournisseur
 * actif) reste lue : elle est traitée comme la clé du fournisseur qui était
 * actif, puis migrée dans `llmKeysEnc` au prochain enregistrement.
 * Fonctions pures (pas d'accès base) pour rester testables.
 */

import type { ProviderName } from '../config.js'

export const LLM_PROVIDERS: readonly ProviderName[] = ['openrouter', 'anthropic', 'openai']

export type EncKeys = Partial<Record<ProviderName, string>>

export interface KeyRow {
  llmProvider: string
  llmApiKeyEnc: string | null
  llmKeysEnc: unknown
}

function isProvider(value: string): value is ProviderName {
  return (LLM_PROVIDERS as readonly string[]).includes(value)
}

/** Lit le JSON stocké en base en ignorant tout ce qui n'est pas « fournisseur connu -> texte chiffré ». */
export function parseKeys(json: unknown): EncKeys {
  if (!json || typeof json !== 'object' || Array.isArray(json)) return {}
  const out: EncKeys = {}
  for (const [provider, enc] of Object.entries(json)) {
    if (isProvider(provider) && typeof enc === 'string' && enc) out[provider] = enc
  }
  return out
}

/** Clés chiffrées effectives : le JSON, plus l'ancienne clé unique sous le fournisseur qui était actif. */
export function effectiveEncKeys(row: KeyRow): EncKeys {
  const keys = parseKeys(row.llmKeysEnc)
  if (row.llmApiKeyEnc && isProvider(row.llmProvider) && !keys[row.llmProvider]) {
    keys[row.llmProvider] = row.llmApiKeyEnc
  }
  return keys
}

/** Pose (chaîne chiffrée) ou efface (null) la clé d'UN fournisseur ; les autres ne bougent pas. */
export function withKey(keys: EncKeys, provider: ProviderName, encrypted: string | null): EncKeys {
  const next: EncKeys = { ...keys }
  if (encrypted) next[provider] = encrypted
  else delete next[provider]
  return next
}

export type KeySource = 'ui' | 'env' | 'both' | 'none'

export function keySource(hasUiKey: boolean, hasEnvKey: boolean): KeySource {
  if (hasUiKey && hasEnvKey) return 'both'
  if (hasUiKey) return 'ui'
  if (hasEnvKey) return 'env'
  return 'none'
}
