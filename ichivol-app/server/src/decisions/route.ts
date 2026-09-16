import type { Request, Response } from 'express'
import { db } from '../db.js'
import { createNotification } from '../notifications/create.js'

const STATUSES = new Set(['confirmed', 'dismissed', 'archived'])

function parseCreate(body: unknown):
  | {
      ok: true
      data: {
        symbol: string
        interval: string
        bias: string
        rvol: number
        signalKind?: string
        gateDecision?: string
        confidence?: number
        note?: string
      }
    }
  | { ok: false; error: string } {
  if (!body || typeof body !== 'object' || Array.isArray(body)) {
    return { ok: false, error: 'Body JSON requis' }
  }
  const raw = body as Record<string, unknown>
  if (typeof raw.symbol !== 'string' || !raw.symbol.trim()) {
    return { ok: false, error: 'symbol requis' }
  }
  if (typeof raw.interval !== 'string' || !raw.interval.trim()) {
    return { ok: false, error: 'interval requis' }
  }
  if (typeof raw.bias !== 'string' || !raw.bias.trim()) {
    return { ok: false, error: 'bias requis' }
  }
  const rvol = typeof raw.rvol === 'number' ? raw.rvol : Number(raw.rvol)
  if (!Number.isFinite(rvol)) {
    return { ok: false, error: 'rvol invalide' }
  }
  const data: {
    symbol: string
    interval: string
    bias: string
    rvol: number
    signalKind?: string
    gateDecision?: string
    confidence?: number
    note?: string
  } = {
    symbol: raw.symbol.trim().toUpperCase(),
    interval: raw.interval.trim(),
    bias: raw.bias.trim().toUpperCase(),
    rvol,
  }
  if (typeof raw.signalKind === 'string' && raw.signalKind.trim()) {
    data.signalKind = raw.signalKind.trim()
  }
  if (typeof raw.gateDecision === 'string' && raw.gateDecision.trim()) {
    data.gateDecision = raw.gateDecision.trim()
  }
  if (typeof raw.confidence === 'number' && Number.isFinite(raw.confidence)) {
    data.confidence = raw.confidence
  }
  if (typeof raw.note === 'string') {
    data.note = raw.note.trim().slice(0, 500) || undefined
  }
  return { ok: true, data }
}

/** GET /api/decisions — journal utilisateur (récent d’abord). */
export async function handleListDecisions(req: Request, res: Response): Promise<void> {
  if (!req.user) {
    res.status(401).json({ error: 'Non authentifié' })
    return
  }
  const limitRaw = Number(req.query.limit ?? 50)
  const limit = Number.isFinite(limitRaw) ? Math.min(Math.max(limitRaw, 1), 100) : 50
  const rows = await db.decision.findMany({
    where: { userId: req.user.id },
    orderBy: { createdAt: 'desc' },
    take: limit,
  })
  res.json({ rows })
}

/** POST /api/decisions — confirmer / journaliser une lecture moteur.
 * Idempotent : un seul `confirmed` par (user, symbole, timeframe).
 * Re-confirm → met à jour le snapshot existant (pas de doublon).
 */
export async function handleCreateDecision(req: Request, res: Response): Promise<void> {
  if (!req.user) {
    res.status(401).json({ error: 'Non authentifié' })
    return
  }
  const parsed = parseCreate(req.body)
  if (!parsed.ok) {
    res.status(400).json({ error: parsed.error })
    return
  }

  const existing = await db.decision.findFirst({
    where: {
      userId: req.user.id,
      symbol: parsed.data.symbol,
      interval: parsed.data.interval,
      status: 'confirmed',
    },
    orderBy: { createdAt: 'desc' },
  })

  if (existing) {
    const prevGate = existing.gateDecision
    const row = await db.decision.update({
      where: { id: existing.id },
      data: {
        bias: parsed.data.bias,
        rvol: parsed.data.rvol,
        signalKind: parsed.data.signalKind ?? existing.signalKind,
        gateDecision: parsed.data.gateDecision ?? existing.gateDecision,
        confidence: parsed.data.confidence ?? existing.confidence,
        note: parsed.data.note ?? existing.note,
      },
    })
    const nextGate = row.gateDecision
    if (nextGate && prevGate && nextGate !== prevGate) {
      await createNotification({
        userId: req.user.id,
        kind: 'pipeline_change',
        title: `${row.symbol} · portes mises à jour`,
        body: `${prevGate} → ${nextGate} (${row.interval}).`,
        payload: {
          decisionId: row.id,
          symbol: row.symbol,
          interval: row.interval,
          prevGate,
          nextGate,
        },
      })
    }
    res.status(200).json({ ...row, deduped: true })
    return
  }

  const row = await db.decision.create({
    data: {
      userId: req.user.id,
      ...parsed.data,
      status: 'confirmed',
    },
  })
  await createNotification({
    userId: req.user.id,
    kind: 'journal_confirm',
    title: `${row.symbol} · au journal`,
    body: `Confirmé en observation (${row.interval}${row.gateDecision ? ` · ${row.gateDecision}` : ''}).`,
    payload: {
      decisionId: row.id,
      symbol: row.symbol,
      interval: row.interval,
      gateDecision: row.gateDecision,
    },
  })
  res.status(201).json({ ...row, deduped: false })
}

/** PATCH /api/decisions/:id — statut (dismissed / archived / confirmed). */
export async function handlePatchDecision(req: Request, res: Response): Promise<void> {
  if (!req.user) {
    res.status(401).json({ error: 'Non authentifié' })
    return
  }
  const id = req.params.id
  if (!id) {
    res.status(400).json({ error: 'id requis' })
    return
  }
  const body = req.body as Record<string, unknown> | null
  const status = body && typeof body.status === 'string' ? body.status : null
  if (!status || !STATUSES.has(status)) {
    res.status(400).json({ error: 'status invalide (confirmed|dismissed|archived)' })
    return
  }
  const existing = await db.decision.findFirst({ where: { id, userId: req.user.id } })
  if (!existing) {
    res.status(404).json({ error: 'Décision introuvable' })
    return
  }
  const row = await db.decision.update({
    where: { id },
    data: { status },
  })
  res.json(row)
}

/** POST /api/decisions/:id/status — même chose que PATCH (évite proxies qui droppent PATCH). */
export async function handlePostDecisionStatus(req: Request, res: Response): Promise<void> {
  return handlePatchDecision(req, res)
}

/** DELETE /api/decisions/:id — suppression définitive. */
export async function handleDeleteDecision(req: Request, res: Response): Promise<void> {
  if (!req.user) {
    res.status(401).json({ error: 'Non authentifié' })
    return
  }
  const id = req.params.id
  if (!id) {
    res.status(400).json({ error: 'id requis' })
    return
  }
  const existing = await db.decision.findFirst({ where: { id, userId: req.user.id } })
  if (!existing) {
    res.status(404).json({ error: 'Décision introuvable' })
    return
  }
  await db.decision.delete({ where: { id } })
  res.json({ ok: true, id })
}
