/**
 * Sessions FX Tokyo / Londres / New York — horaires en heure locale de place + fuseau IANA.
 * Le passage heure d’été / d’hiver est géré automatiquement via Intl.
 * Positions % = ancrage carte world-map (layout), pas des métriques marché.
 */

export type SessionId =
  | 'sydney'
  | 'hongkong'
  | 'singapore'
  | 'tokyo'
  | 'frankfurt'
  | 'london'
  | 'newyork'
  | 'chicago'
  | 'crypto'

export type SessionStatus = 'open' | 'closed' | 'upcoming'

export type SessionKind = 'cash' | 'futures_cme' | 'always'

export type MarketSessionDef = {
  id: SessionId
  region: string
  city: string
  venue: string
  /** IANA timezone of the venue. */
  timeZone: string
  kind: SessionKind
  /** Local open hour (decimal, e.g. 9.5 = 09:30). Cash sessions only. */
  openLocal: number
  /** Local close hour (exclusive end as decimal). Cash sessions only. */
  closeLocal: number
  /** Marker position on world-map.svg (percent). */
  mapLeftPct: number
  mapTopPct: number
}

export const MARKET_SESSIONS: MarketSessionDef[] = [
  {
    id: 'sydney',
    region: 'Sydney',
    city: 'Sydney',
    venue: 'ASX',
    timeZone: 'Australia/Sydney',
    kind: 'cash',
    openLocal: 10,
    closeLocal: 16,
    mapLeftPct: 84,
    mapTopPct: 72,
  },
  {
    id: 'hongkong',
    region: 'Hong Kong',
    city: 'Hong Kong',
    venue: 'HKEX',
    timeZone: 'Asia/Hong_Kong',
    kind: 'cash',
    openLocal: 9.5,
    closeLocal: 16,
    mapLeftPct: 74.2,
    mapTopPct: 42,
  },
  {
    id: 'singapore',
    region: 'Singapour',
    city: 'Singapour',
    venue: 'SGX',
    timeZone: 'Asia/Singapore',
    kind: 'cash',
    openLocal: 9,
    closeLocal: 17,
    mapLeftPct: 72.4,
    mapTopPct: 56,
  },
  {
    id: 'tokyo',
    region: 'Tokyo',
    city: 'Tokyo',
    venue: 'TSE',
    timeZone: 'Asia/Tokyo',
    kind: 'cash',
    openLocal: 9,
    closeLocal: 15,
    mapLeftPct: 77.6,
    mapTopPct: 34.6,
  },
  {
    id: 'frankfurt',
    region: 'Francfort',
    city: 'Francfort',
    venue: 'Xetra',
    timeZone: 'Europe/Berlin',
    kind: 'cash',
    openLocal: 9,
    closeLocal: 17.5,
    mapLeftPct: 51.6,
    mapTopPct: 28,
  },
  {
    id: 'london',
    region: 'Londres',
    city: 'Londres',
    venue: 'LSE',
    timeZone: 'Europe/London',
    kind: 'cash',
    openLocal: 8,
    closeLocal: 16.5,
    mapLeftPct: 48.2,
    mapTopPct: 26,
  },
  {
    id: 'newyork',
    region: 'New York',
    city: 'New York',
    venue: 'NYSE',
    timeZone: 'America/New_York',
    kind: 'cash',
    openLocal: 9.5,
    closeLocal: 16,
    mapLeftPct: 29.4,
    mapTopPct: 34,
  },
  {
    id: 'chicago',
    region: 'Chicago',
    city: 'Chicago',
    venue: 'CME',
    timeZone: 'America/Chicago',
    kind: 'futures_cme',
    openLocal: 17,
    closeLocal: 16,
    mapLeftPct: 23.2,
    mapTopPct: 32,
  },
  {
    id: 'crypto',
    region: 'Crypto',
    city: 'Crypto',
    venue: '24/7',
    timeZone: 'UTC',
    kind: 'always',
    openLocal: 0,
    closeLocal: 24,
    mapLeftPct: 50,
    mapTopPct: 78,
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

function cmeStatus(now: Date): SessionStatus {
  const parts = zonedParts(now, 'America/Chicago')
  const h = localHourDecimal(parts)
  if (parts.weekday === 6) return 'closed'
  if (parts.weekday === 0) return h >= 17 ? 'open' : 'upcoming'
  if (parts.weekday === 5) return h < 16 ? 'open' : 'closed'
  if (h >= 16 && h < 17) return 'upcoming'
  return 'open'
}

export function sessionStatus(def: MarketSessionDef, now: Date = new Date()): SessionStatus {
  switch (def.kind) {
    case 'always':
      return 'open'
    case 'futures_cme':
      return cmeStatus(now)
    case 'cash': {
      const parts = zonedParts(now, def.timeZone)
      if (isWeekendLocal(parts)) return 'closed'
      const h = localHourDecimal(parts)
      if (inWindow(h, def.openLocal, def.closeLocal)) return 'open'
      if (h < def.openLocal) return 'upcoming'
      return 'closed'
    }
    default: {
      const _e: never = def.kind
      return _e
    }
  }
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

export function formatVenueClock(def: MarketSessionDef, now: Date = new Date()): string {
  return now.toLocaleTimeString('fr-FR', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: def.timeZone,
  })
}

function nextWeekdayOpen(def: MarketSessionDef, now: Date): Date {
  const openH = Math.floor(def.openLocal)
  const openMin = Math.round((def.openLocal - openH) * 60)
  for (let i = 0; i < 8; i++) {
    const probe = new Date(now.getTime() + i * 86_400_000)
    const p = zonedParts(probe, def.timeZone)
    if (p.weekday === 0 || p.weekday === 6) continue
    const open = wallTimeToUtc(p.year, p.month, p.day, openH, openMin, def.timeZone)
    if (open.getTime() > now.getTime() + 30_000) return open
  }
  return now
}

function nextCmeOpen(now: Date): Date {
  const tz = 'America/Chicago'
  for (let i = 0; i < 8; i++) {
    const probe = new Date(now.getTime() + i * 86_400_000)
    const p = zonedParts(probe, tz)
    if (p.weekday === 6 || p.weekday === 5) continue
    const open = wallTimeToUtc(p.year, p.month, p.day, 17, 0, tz)
    if (open.getTime() > now.getTime() + 30_000) return open
  }
  return now
}

/** Next opening, or null when the venue does not close. */
export function nextSessionOpen(def: MarketSessionDef, now: Date = new Date()): Date | null {
  if (def.kind === 'always') return null
  if (sessionStatus(def, now) === 'open') return null
  if (def.kind === 'futures_cme') return nextCmeOpen(now)
  return nextWeekdayOpen(def, now)
}

/** Format open–close in UTC (maquette Desk session detail). */
export function formatSessionHoursUtc(def: MarketSessionDef, now: Date = new Date()): string {
  if (def.kind === 'always') return 'Continu'
  if (def.kind === 'futures_cme') return 'Dim 17:00 – Ven 16:00 CT'
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
