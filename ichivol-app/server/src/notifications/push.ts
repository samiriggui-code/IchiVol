/** T0-NOTIF — Web Push sender (never throws; mirrors mailer.ts). */

import webpush from 'web-push'
import { config } from '../config.js'
import { db } from '../db.js'

let warnedMissing = false
let vapidConfigured = false

function ensureVapid(): boolean {
  if (!config.vapid.publicKey || !config.vapid.privateKey) {
    if (!warnedMissing) {
      console.warn(
        '[push] VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY non configurés — push désactivé.',
      )
      warnedMissing = true
    }
    return false
  }
  if (!vapidConfigured) {
    webpush.setVapidDetails(
      config.vapid.subject,
      config.vapid.publicKey,
      config.vapid.privateKey,
    )
    vapidConfigured = true
  }
  return true
}

export type PushPayload = {
  title: string
  body: string
  url?: string
  tag?: string
  data?: Record<string, unknown>
}

/**
 * Never throws. Returns whether at least one device received the push.
 * Gone/invalid subscriptions (404/410) are deleted silently.
 */
export async function sendPushToUser(
  userId: string,
  payload: PushPayload,
): Promise<boolean> {
  if (!ensureVapid()) return false
  const subs = await db.pushSubscription.findMany({ where: { userId } })
  if (subs.length === 0) return false

  const body = JSON.stringify(payload)
  let anyOk = false
  for (const sub of subs) {
    try {
      await webpush.sendNotification(
        {
          endpoint: sub.endpoint,
          keys: { p256dh: sub.p256dh, auth: sub.auth },
        },
        body,
        { TTL: 60 * 60 },
      )
      anyOk = true
      await db.pushSubscription
        .update({ where: { id: sub.id }, data: { lastUsedAt: new Date() } })
        .catch(() => undefined)
    } catch (err: unknown) {
      const status =
        err && typeof err === 'object' && 'statusCode' in err
          ? Number((err as { statusCode?: number }).statusCode)
          : undefined
      if (status === 404 || status === 410) {
        await db.pushSubscription
          .delete({ where: { id: sub.id } })
          .catch(() => undefined)
      } else {
        const msg = err instanceof Error ? err.message : String(err)
        console.error('[push] envoi échoué:', msg)
      }
    }
  }
  return anyOk
}

/** Test helper — send to one raw subscription shape; never throws. */
export async function sendPushRaw(
  subscription: { endpoint: string; keys: { p256dh: string; auth: string } },
  payload: PushPayload,
): Promise<{ ok: boolean; gone: boolean }> {
  if (!ensureVapid()) return { ok: false, gone: false }
  try {
    await webpush.sendNotification(subscription, JSON.stringify(payload), {
      TTL: 60,
    })
    return { ok: true, gone: false }
  } catch (err: unknown) {
    const status =
      err && typeof err === 'object' && 'statusCode' in err
        ? Number((err as { statusCode?: number }).statusCode)
        : undefined
    if (status === 404 || status === 410) return { ok: false, gone: true }
    console.error(
      '[push] sendPushRaw échoué:',
      err instanceof Error ? err.message : err,
    )
    return { ok: false, gone: false }
  }
}
