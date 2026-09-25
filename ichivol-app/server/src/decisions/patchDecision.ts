/** Logique pure PATCH décision — testable sans Prisma. */

const STATUSES = new Set(['confirmed', 'dismissed', 'archived'])

export type PatchDecisionData = {
  status?: string
  note?: string | null
}

export type PatchParseResult =
  | { ok: true; data: PatchDecisionData }
  | { ok: false; error: string; status: number }

/** Normalise note : trim, max 500, vide → null. */
export function normalizeDecisionNote(raw: unknown): string | null | { error: string } {
  if (raw === null) return null
  if (typeof raw !== 'string') return { error: 'note invalide (string ou null)' }
  const trimmed = raw.trim().slice(0, 500)
  return trimmed.length === 0 ? null : trimmed
}

/**
 * Parse body PATCH : status et/ou note.
 * Ownership (userId) est vérifié côté handler avant update.
 */
export function parsePatchDecisionBody(body: unknown): PatchParseResult {
  if (!body || typeof body !== 'object' || Array.isArray(body)) {
    return { ok: false, error: 'status ou note requis', status: 400 }
  }
  const raw = body as Record<string, unknown>
  const hasStatus = typeof raw.status === 'string'
  const hasNote = Object.prototype.hasOwnProperty.call(raw, 'note')

  if (!hasStatus && !hasNote) {
    return { ok: false, error: 'status ou note requis', status: 400 }
  }

  const data: PatchDecisionData = {}

  if (hasStatus) {
    const status = raw.status as string
    if (!STATUSES.has(status)) {
      return {
        ok: false,
        error: 'status invalide (confirmed|dismissed|archived)',
        status: 400,
      }
    }
    data.status = status
  }

  if (hasNote) {
    const note = normalizeDecisionNote(raw.note)
    if (note && typeof note === 'object' && 'error' in note) {
      return { ok: false, error: note.error, status: 400 }
    }
    data.note = note as string | null
  }

  return { ok: true, data }
}

/** True si la ligne appartient à l’utilisateur (sinon 404 — pas de fuite). */
export function decisionOwnedByUser(
  row: { userId: string } | null | undefined,
  userId: string,
): boolean {
  return Boolean(row && row.userId === userId)
}
