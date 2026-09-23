/** Pure dedup helpers for T0-NOTIF (no config / DB imports). */

export function shouldEmitAlert(opts: {
  last: { createdAt: Date; band?: string | null; stateKey?: string | null } | null
  now: Date
  cooldownMin: number
  band?: string | null
  stateKey?: string | null
}): boolean {
  if (!opts.last) return true
  const ageMs = opts.now.getTime() - opts.last.createdAt.getTime()
  const coolMs = opts.cooldownMin * 60_000
  if (ageMs >= coolMs) return true
  if (
    opts.band != null &&
    opts.last.band != null &&
    Number(opts.band) < Number(opts.last.band)
  ) {
    return true
  }
  if (
    opts.stateKey != null &&
    opts.last.stateKey != null &&
    opts.stateKey !== opts.last.stateKey
  ) {
    return true
  }
  return false
}
