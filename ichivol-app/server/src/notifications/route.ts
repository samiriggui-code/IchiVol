import type { Request, Response } from 'express'
import { db } from '../db.js'

/** GET /api/notifications?unread=1&limit=40 */
export async function handleListNotifications(req: Request, res: Response): Promise<void> {
  if (!req.user) {
    res.status(401).json({ error: 'Non authentifié' })
    return
  }
  const limitRaw = Number(req.query.limit ?? 40)
  const limit = Number.isFinite(limitRaw) ? Math.min(Math.max(limitRaw, 1), 100) : 40
  const unreadOnly = req.query.unread === '1' || req.query.unread === 'true'

  const rows = await db.notification.findMany({
    where: {
      userId: req.user.id,
      ...(unreadOnly ? { readAt: null } : {}),
    },
    orderBy: { createdAt: 'desc' },
    take: limit,
  })

  const unreadCount = await db.notification.count({
    where: { userId: req.user.id, readAt: null },
  })

  res.json({ rows, unreadCount })
}

/** POST /api/notifications/:id/read */
export async function handleReadNotification(req: Request, res: Response): Promise<void> {
  if (!req.user) {
    res.status(401).json({ error: 'Non authentifié' })
    return
  }
  const id = req.params.id
  if (!id) {
    res.status(400).json({ error: 'id requis' })
    return
  }
  const existing = await db.notification.findFirst({
    where: { id, userId: req.user.id },
  })
  if (!existing) {
    res.status(404).json({ error: 'Notification introuvable' })
    return
  }
  if (existing.readAt) {
    res.json(existing)
    return
  }
  const row = await db.notification.update({
    where: { id },
    data: { readAt: new Date() },
  })
  res.json(row)
}

/** POST /api/notifications/read-all */
export async function handleReadAllNotifications(req: Request, res: Response): Promise<void> {
  if (!req.user) {
    res.status(401).json({ error: 'Non authentifié' })
    return
  }
  const result = await db.notification.updateMany({
    where: { userId: req.user.id, readAt: null },
    data: { readAt: new Date() },
  })
  res.json({ ok: true, updated: result.count })
}
