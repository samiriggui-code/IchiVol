/** T0-NOTIF — push subscribe/unsubscribe + VAPID public key. */

import type { Request, Response } from 'express'
import { config } from '../config.js'
import { db } from '../db.js'

/** GET /api/notifications/push-vapid-public */
export async function handlePushVapidPublic(
  _req: Request,
  res: Response,
): Promise<void> {
  if (!config.vapid.publicKey) {
    res.status(503).json({
      error: 'push_not_configured',
      message:
        'VAPID_PUBLIC_KEY manquant côté serveur — alertes push indisponibles.',
    })
    return
  }
  res.json({
    publicKey: config.vapid.publicKey,
    subject: config.vapid.subject,
  })
}

/** POST /api/notifications/push-subscribe */
export async function handlePushSubscribe(
  req: Request,
  res: Response,
): Promise<void> {
  if (!req.user) {
    res.status(401).json({ error: 'Non authentifié' })
    return
  }
  const body = req.body as {
    endpoint?: unknown
    keys?: { p256dh?: unknown; auth?: unknown }
    expirationTime?: unknown
  }
  const endpoint = typeof body.endpoint === 'string' ? body.endpoint.trim() : ''
  const p256dh =
    body.keys && typeof body.keys.p256dh === 'string' ? body.keys.p256dh : ''
  const auth =
    body.keys && typeof body.keys.auth === 'string' ? body.keys.auth : ''
  if (!endpoint || !p256dh || !auth) {
    res.status(400).json({ error: 'endpoint + keys.p256dh + keys.auth requis' })
    return
  }
  const userAgent =
    typeof req.headers['user-agent'] === 'string'
      ? req.headers['user-agent'].slice(0, 400)
      : null

  const row = await db.pushSubscription.upsert({
    where: {
      userId_endpoint: { userId: req.user.id, endpoint },
    },
    create: {
      userId: req.user.id,
      endpoint,
      p256dh,
      auth,
      userAgent,
      lastUsedAt: new Date(),
    },
    update: {
      p256dh,
      auth,
      userAgent,
      lastUsedAt: new Date(),
    },
  })
  res.json({
    ok: true,
    id: row.id,
    endpoint: row.endpoint,
  })
}

/** DELETE /api/notifications/push-subscribe */
export async function handlePushUnsubscribe(
  req: Request,
  res: Response,
): Promise<void> {
  if (!req.user) {
    res.status(401).json({ error: 'Non authentifié' })
    return
  }
  const endpoint =
    typeof (req.body as { endpoint?: unknown })?.endpoint === 'string'
      ? String((req.body as { endpoint: string }).endpoint).trim()
      : ''
  if (!endpoint) {
    res.status(400).json({ error: 'endpoint requis' })
    return
  }
  await db.pushSubscription.deleteMany({
    where: { userId: req.user.id, endpoint },
  })
  res.json({ ok: true })
}
