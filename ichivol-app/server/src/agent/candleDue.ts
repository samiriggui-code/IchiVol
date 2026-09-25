/**
 * Chantier 2 E1 — next closed candle + grace (audit: dueAt = close + 60s).
 * Closed-only evaluation; no open-bar wake.
 */

const TF_SECONDS: Record<string, number> = {
  '15m': 900,
  '1h': 3600,
  '4h': 14400,
  '1d': 86400,
}

/** Grace after candle close before the recheck is due (engine delivery lag). */
export const CANDLE_GRACE_MS = 60_000

export function timeframeSeconds(tf: string): number {
  const sec = TF_SECONDS[tf.trim().toLowerCase()]
  if (!sec) throw new Error(`unsupported_timeframe: ${tf}`)
  return sec
}

/**
 * Next closed-candle dueAt = end of current bar + 60s.
 * If already past grace into the next bar, schedules the following close + grace.
 */
export function nextClosedCandleDueAt(timeframe: string, now: Date = new Date()): Date {
  const sec = timeframeSeconds(timeframe)
  const nowSec = Math.floor(now.getTime() / 1000)
  const barStart = Math.floor(nowSec / sec) * sec
  const closeSec = barStart + sec
  let dueMs = closeSec * 1000 + CANDLE_GRACE_MS
  if (dueMs <= now.getTime()) {
    dueMs += sec * 1000
  }
  return new Date(dueMs)
}

/** Push dueAt forward by one bar (+ grace) from a reference time. */
export function deferOneBar(timeframe: string, from: Date = new Date()): Date {
  const sec = timeframeSeconds(timeframe)
  return new Date(from.getTime() + sec * 1000)
}
