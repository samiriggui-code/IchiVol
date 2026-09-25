/** Journal utilisateur des décisions confirmées (Prisma /api/decisions — pas la DB engine). */

export interface UserDecisionRow {
  id: string
  symbol: string
  interval: string
  bias: string
  rvol: number
  signalKind: string | null
  gateDecision: string | null
  confidence: number | null
  note: string | null
  status: string
  createdAt: string
  updatedAt?: string
}

export interface ConfirmDecisionPayload {
  symbol: string
  interval: string
  bias: string
  rvol: number
  signalKind?: string
  gateDecision?: string
  confidence?: number
  note?: string
}

async function parseError(res: Response): Promise<string> {
  const body = (await res.json().catch(() => null)) as { error?: string; message?: string } | null
  return body?.error ?? body?.message ?? `Erreur ${res.status}`
}

export async function listUserDecisions(limit = 40): Promise<UserDecisionRow[]> {
  const res = await fetch(`/api/decisions?limit=${limit}`, { credentials: 'include' })
  if (!res.ok) throw new Error(await parseError(res))
  const body = (await res.json()) as { rows: UserDecisionRow[] }
  return body.rows
}

export async function confirmUserDecision(
  payload: ConfirmDecisionPayload,
): Promise<UserDecisionRow & { deduped?: boolean }> {
  const res = await fetch('/api/decisions', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<UserDecisionRow & { deduped?: boolean }>
}

export async function patchUserDecisionStatus(
  id: string,
  status: 'confirmed' | 'dismissed' | 'archived',
): Promise<UserDecisionRow> {
  // POST (pas PATCH) — certains proxies / stacks droppent PATCH.
  const res = await fetch(`/api/decisions/${encodeURIComponent(id)}/status`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<UserDecisionRow>
}

/** Note personnelle — PATCH par id (pas d’upsert : pas de doublon archivé). */
export async function patchUserDecisionNote(id: string, note: string): Promise<UserDecisionRow> {
  const trimmed = note.trim().slice(0, 500)
  const res = await fetch(`/api/decisions/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ note: trimmed }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<UserDecisionRow>
}

export async function deleteUserDecision(id: string): Promise<void> {
  const res = await fetch(`/api/decisions/${encodeURIComponent(id)}`, {
    method: 'DELETE',
    credentials: 'include',
  })
  if (!res.ok) throw new Error(await parseError(res))
}
