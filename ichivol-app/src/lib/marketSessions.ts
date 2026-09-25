/**
 * Sessions FX Tokyo / Londres / New York — statut calculé côté front (UTC).
 * Positions % = ancrage carte world-map (layout), pas des métriques marché.
 */

export type SessionId = 'tokyo' | 'london' | 'newyork'

export type SessionStatus = 'open' | 'closed' | 'upcoming'

export type MarketSessionDef = {
  id: SessionId
  region: string
  city: string
  /** Start hour UTC (decimal, e.g. 13.5 = 13:30). */
  openUtc: number
  /** End hour UTC (exclusive window end as decimal). */
  closeUtc: number
  /** Marker position on world-map.svg (percent). */
  mapLeftPct: number
  mapTopPct: number
}

export const MARKET_SESSIONS: MarketSessionDef[] = [
  {
    id: 'tokyo',
    region: 'Asie',
    city: 'Tokyo',
    openUtc: 0,
    closeUtc: 9,
    mapLeftPct: 77.6,
    mapTopPct: 34.6,
  },
  {
    id: 'london',
    region: 'Europe',
    city: 'Londres',
    openUtc: 7,
    closeUtc: 16,
    mapLeftPct: 50,
    mapTopPct: 23.1,
  },
  {
    id: 'newyork',
    region: 'États-Unis',
    city: 'New York',
    openUtc: 13.5,
    closeUtc: 20,
    mapLeftPct: 29.4,
    mapTopPct: 30.6,
  },
]

function utcHourDecimal(d: Date): number {
  return d.getUTCHours() + d.getUTCMinutes() / 60 + d.getUTCSeconds() / 3600
}

function isWeekendUtc(d: Date): boolean {
  const day = d.getUTCDay()
  return day === 0 || day === 6
}

/** True if `hour` is in [open, close) handling same-day windows only. */
function inWindow(hour: number, open: number, close: number): boolean {
  return hour >= open && hour < close
}

export function sessionStatus(def: MarketSessionDef, now: Date = new Date()): SessionStatus {
  if (isWeekendUtc(now)) return 'closed'
  const h = utcHourDecimal(now)
  if (inWindow(h, def.openUtc, def.closeUtc)) return 'open'
  if (h < def.openUtc) return 'upcoming'
  return 'closed'
}

export function sessionStatusLabel(status: SessionStatus): string {
  switch (status) {
    case 'open':
      return 'Ouverte'
    case 'closed':
      return 'Clôturée'
    case 'upcoming':
      return 'À venir'
    default: {
      const _e: never = status
      return _e
    }
  }
}

/** Format open–close in the user's local timezone. */
export function formatSessionHoursLocal(def: MarketSessionDef, now: Date = new Date()): string {
  const y = now.getUTCFullYear()
  const m = now.getUTCMonth()
  const day = now.getUTCDate()
  const openH = Math.floor(def.openUtc)
  const openMin = Math.round((def.openUtc - openH) * 60)
  const closeH = Math.floor(def.closeUtc)
  const closeMin = Math.round((def.closeUtc - closeH) * 60)
  const open = new Date(Date.UTC(y, m, day, openH, openMin, 0))
  const close = new Date(Date.UTC(y, m, day, closeH, closeMin, 0))
  const fmt = (d: Date) =>
    d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
  return `${fmt(open)}–${fmt(close)}`
}

/** Next 1h candle close (UTC hour boundary). */
export function nextHourlyClose(now: Date = new Date()): Date {
  const d = new Date(now.getTime())
  d.setUTCMinutes(0, 0, 0)
  d.setUTCHours(d.getUTCHours() + 1)
  return d
}

export function formatCountdown(to: Date, now: Date = new Date()): string {
  const ms = Math.max(0, to.getTime() - now.getTime())
  const m = Math.floor(ms / 60_000)
  const s = Math.floor((ms % 60_000) / 1000)
  if (m >= 60) {
    const h = Math.floor(m / 60)
    return `${h} h ${m % 60} min`
  }
  return `${m} min ${String(s).padStart(2, '0')} s`
}
