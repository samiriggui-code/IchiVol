/**
 * Health watchdog (CDC "notifications/alertes si ça crash, API injoignable
 * etc", 2026-09-17). Polls the exact same check GET /api/health uses
 * (health/check.ts) on an interval, and only fires when the state actually
 * CHANGES -- healthy -> unhealthy sends the alert once, not every poll
 * while it stays down (that would spam), and unhealthy -> healthy sends a
 * "recovered" notice so a silent self-heal doesn't go unnoticed either.
 */
import { render } from '@react-email/render'
import { config } from '../config.js'
import { db } from '../db.js'
import { checkSystemHealth, isHealthy, type SystemHealth } from '../health/check.js'
import { AlertEmail } from './emails/AlertEmail.js'
import { sendMail } from './mailer.js'

let lastKnownHealthy: boolean | null = null
let timer: NodeJS.Timeout | null = null

async function notifyAllUsers(kind: 'system_alert', title: string, body: string): Promise<void> {
  const users = await db.user.findMany({ select: { id: true } })
  await Promise.all(
    users.map((u) =>
      db.notification.create({ data: { userId: u.id, kind, title, body } }),
    ),
  )
}

async function handleTransition(health: SystemHealth, healthy: boolean): Promise<void> {
  const checkedAt = new Date().toLocaleString('fr-FR', { timeZone: 'Europe/Paris' })

  if (!healthy) {
    const downParts = [!health.database && 'base de données', !health.engine && 'moteur Python']
      .filter(Boolean)
      .join(', ')
    await notifyAllUsers(
      'system_alert',
      'Système en panne',
      `${downParts} injoignable(s) depuis ${checkedAt}.`,
    )
    if (config.alertEmailTo) {
      const html = await render(
        AlertEmail({
          database: health.database,
          engine: health.engine,
          checkedAt,
          appUrl: config.engineUrl.replace(':8000', ''),
        }),
      )
      await sendMail({ to: config.alertEmailTo, subject: '🔴 IchiVol — système en panne', html })
    }
    return
  }

  // Recovery notice -- only sent if we previously knew it was down (not on
  // the very first check at process boot, which would falsely claim a
  // "recovery" from nothing).
  if (lastKnownHealthy === false) {
    await notifyAllUsers('system_alert', 'Système rétabli', `Tout répond de nouveau depuis ${checkedAt}.`)
    if (config.alertEmailTo) {
      const html = await render(
        AlertEmail({ database: true, engine: true, checkedAt, appUrl: config.engineUrl.replace(':8000', '') }),
      )
      await sendMail({ to: config.alertEmailTo, subject: '✅ IchiVol — système rétabli', html })
    }
  }
}

async function tick(): Promise<void> {
  try {
    const health = await checkSystemHealth()
    const healthy = isHealthy(health)
    if (healthy !== lastKnownHealthy) {
      await handleTransition(health, healthy)
    }
    lastKnownHealthy = healthy
  } catch (err) {
    console.error('[watchdog] tick a échoué:', err instanceof Error ? err.message : err)
  }
}

export function startSystemWatchdog(): void {
  if (timer) return
  void tick()
  timer = setInterval(() => void tick(), config.watchdogIntervalMs)
}

export function stopSystemWatchdog(): void {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
  lastKnownHealthy = null
}
