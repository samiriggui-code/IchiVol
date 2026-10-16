/** Ève / JEV / Event Radar settings — schema-driven (QuantDinger Basic/Advanced). */

export type EveSettingType = 'text' | 'password' | 'number' | 'boolean'

export interface EveSettingItem {
  key: string
  label: string
  type: EveSettingType
  description?: string
  default?: string | number | boolean
  read_only?: boolean
  is_advanced?: boolean
  writable?: boolean
}

export interface EveSettingGroup {
  title: string
  order?: number
  items: EveSettingItem[]
}

export interface EveSettingsSchemaResponse {
  schema_version: string
  schema: Record<string, EveSettingGroup>
  advanced_keys: string[]
  writable_keys: string[]
  note?: string
}

export interface EveSettingsValuesResponse {
  schema_version: string
  values: Record<string, string | number | boolean>
  writable_keys: string[]
}

async function parseError(res: Response): Promise<string> {
  const body = (await res.json().catch(() => null)) as
    | { detail?: string; error?: string; message?: string }
    | null
  if (body?.detail) return typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
  return body?.error ?? body?.message ?? `Erreur ${res.status}`
}

export async function getEveSettingsSchema(): Promise<EveSettingsSchemaResponse> {
  const res = await fetch('/api/engine/eve/settings/schema', { credentials: 'include' })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<EveSettingsSchemaResponse>
}

export async function getEveSettingsValues(): Promise<EveSettingsValuesResponse> {
  const res = await fetch('/api/engine/eve/settings/values', { credentials: 'include' })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<EveSettingsValuesResponse>
}

export async function patchEveSettingsValues(
  patch: Record<string, string | number | boolean>,
): Promise<{ values: Record<string, string | number | boolean> }> {
  const res = await fetch('/api/engine/eve/settings/values', {
    method: 'PATCH',
    credentials: 'include',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(patch),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<{ values: Record<string, string | number | boolean> }>
}

export function sortedSchemaGroups(
  schema: Record<string, EveSettingGroup>,
): Array<[string, EveSettingGroup]> {
  return Object.entries(schema).sort(
    (a, b) => (a[1].order ?? 99) - (b[1].order ?? 99),
  )
}
