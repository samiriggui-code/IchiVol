/**
 * Sessions FX Tokyo / Londres / New York — horaires en heure locale de place + fuseau IANA.
 * Le passage heure d’été / d’hiver est géré automatiquement via Intl.
 * Positions % = ancrage carte world-map (layout), pas des métriques marché.
 */

export type SessionId = 'tokyo' | 'london' | 'newyork'

export type SessionStatus = 'open' | 'closed' | 'upcoming'

export type MarketSessionDef = {
  id: SessionId
  region: string
  city: string
  /** IANA timezone of the venue. */
  timeZone: string
  /** Local open hour (decimal, e.g. 9.5 = 09:30). */
  openLocal: number
  /** Local close hour (exclusive end as decimal). */
  closeLocal: number
  /** Marker position on world-map.svg (percent). */
  mapLeftPct: number
  mapTopPct: number
}

export const MARKET_SESSIONS: MarketSessionDef[] = [
  {
    id: 'tokyo',
    region: 'Asie',
    city: 'Tokyo',
    timeZone: 'Asia/Tokyo',
    openLocal: 9,
    closeLocal: 18,
    mapLeftPct: 77.6,
    mapTopPct: 34.6,
  },
  {
    id: 'london',
    region: 'Europe',
    city: 'Londres',
    timeZone: 'Europe/London',
    openLocal: 8,
    closeLocal: 17,
    mapLeftPct: 50,
    mapTopPct: 23.1,
  },
  {
    id: 'newyork',
    region: 'États-Unis',
    city: 'New York',
    timeZone: 'America/New_York',
    openLocal: 9.5,
    closeLocal: 16,
    mapLeftPct: 29.4,
    mapTopPct: 30.6,
  },
]

type ZonedParts = {
  year: number
  month: number
  day: number
  hour: number
  minute: number
  second: number
  weekday: number
}

const WEEKDAY_INDEX: Record<string, number> = {
  Sun: 0,
  Mon: 1,
  Tue: 2,
  Wed: 3,
  Thu: 4,
  Fri: 5,
  Sat: 6,
}

function zonedParts(date: Date, timeZone: string): ZonedParts {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    weekday: 'short',
    hourCycle: 'h23',
  }).formatToParts(date)

  const get = (type: Intl.DateTimeFormatPartTypes): string =>
    parts.find((p) => p.type === type)?.value ?? '0'

  const wd = get('weekday')
  return {
    year: Number(get('year')),
    month: Number(get('month')),
    day: Number(get('day')),
    hour: Number(get('hour')),
    minute: Number(get('minute')),
    second: Number(get('second')),
    weekday: WEEKDAY_INDEX[wd] ?? 0,
  }
}

function localHourDecimal(parts: ZonedParts): number {
  return parts.hour + parts.minute / 60 + parts.second / 3600
}

function isWeekendLocal(parts: ZonedParts): boolean {
  return parts.weekday === 0 || parts.weekday === 6
}

/** True if `hour` is in [open, close) handling same-day windows only. */
function inWindow(hour: number, open: number, close: number): boolean {
  return hour >= open && hour < close
}

/**
 * Convert a wall-clock time in `timeZone` to an absolute Date.
 * Iterates to absorb DST offsets.
 */
export function wallTimeToUtc(
  year: number,
  month: number,
  day: number,
  hour: number,
  minute: number,
  timeZone: string,
): Date {
  let guess = Date.UTC(year, month - 1, day, hour, minute, 0)
  for (let i = 0; i < 4; i++) {
    const p = zonedParts(new Date(guess), timeZone)
    const asUtc = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second)
    const desired = Date.UTC(year, month - 1, day, hour, minute, 0)
    const delta = desired - asUtc
    if (delta === 0) break
    guess += delta
  }
  return new Date(guess)
}

export function sessionStatus(def: MarketSessionDef, now: Date = new Date()): SessionStatus {
  const parts = zonedParts(now, def.timeZone)
  if (isWeekendLocal(parts)) return 'closed'
  const h = localHourDecimal(parts)
  if (inWindow(h, def.openLocal, def.closeLocal)) return 'open'
  if (h < def.openLocal) return 'upcoming'
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

function sessionOpenCloseUtc(def: MarketSessionDef, now: Date): { open: Date; close: Date } {
  const p = zonedParts(now, def.timeZone)
  const openH = Math.floor(def.openLocal)
  const openMin = Math.round((def.openLocal - openH) * 60)
  const closeH = Math.floor(def.closeLocal)
  const closeMin = Math.round((def.closeLocal - closeH) * 60)
  return {
    open: wallTimeToUtc(p.year, p.month, p.day, openH, openMin, def.timeZone),
    close: wallTimeToUtc(p.year, p.month, p.day, closeH, closeMin, def.timeZone),
  }
}

/** Format open–close in the user's local timezone (for the venue calendar day of `now`). */
export function formatSessionHoursLocal(def: MarketSessionDef, now: Date = new Date()): string {
  const { open, close } = sessionOpenCloseUtc(def, now)
  const fmt = (d: Date) =>
    d.toLocaleTimeString('fr-FR', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    })
  return `${fmt(open)}–${fmt(close)}`
}

/** Format open–close in UTC (maquette Desk session detail). */
export function formatSessionHoursUtc(def: MarketSessionDef, now: Date = new Date()): string {
  const { open, close } = sessionOpenCloseUtc(def, now)
  const fmt = (d: Date) =>
    d.toLocaleTimeString('fr-FR', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
      timeZone: 'UTC',
    })
  return `${fmt(open)}–${fmt(close)} UTC`
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
