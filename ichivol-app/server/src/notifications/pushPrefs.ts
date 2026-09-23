/** T0-NOTIF — alert prefs helpers (stored on Setting.pushAlertPrefs). */

export type PushAlertPrefs = {
  /** Master toggle — must be true for watcher to emit. */
  enabled: boolean
  targetStop: boolean
  accel: boolean
  directionFlip: boolean
  /** Remaining distance threshold as fraction (default 0.20 = 20 %). */
  nearPct: number
  /** Cooldown minutes between identical kind+position alerts. */
  cooldownMin: number
}

export const DEFAULT_PUSH_ALERT_PREFS: PushAlertPrefs = {
  enabled: false,
  targetStop: true,
  accel: true,
  directionFlip: true,
  nearPct: 0.2,
  cooldownMin: 30,
}

export function parsePushAlertPrefs(raw: unknown): PushAlertPrefs {
  const base = { ...DEFAULT_PUSH_ALERT_PREFS }
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return base
  const o = raw as Record<string, unknown>
  if (typeof o.enabled === 'boolean') base.enabled = o.enabled
  if (typeof o.targetStop === 'boolean') base.targetStop = o.targetStop
  if (typeof o.accel === 'boolean') base.accel = o.accel
  if (typeof o.directionFlip === 'boolean') base.directionFlip = o.directionFlip
  if (typeof o.nearPct === 'number' && o.nearPct > 0 && o.nearPct <= 1) {
    base.nearPct = o.nearPct
  }
  if (typeof o.cooldownMin === 'number' && o.cooldownMin >= 1 && o.cooldownMin <= 24 * 60) {
    base.cooldownMin = Math.floor(o.cooldownMin)
  }
  return base
}
