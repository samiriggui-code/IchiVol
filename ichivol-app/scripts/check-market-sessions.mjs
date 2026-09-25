/**
 * Session status checks — mirrors src/lib/marketSessions.ts (IANA + heures locales).
 * Includes DST transition cases for London (2026-10-25) and New York (2026-11-01).
 */

const WEEKDAY_INDEX = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 }

function zonedParts(date, timeZone) {
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
  const get = (type) => parts.find((p) => p.type === type)?.value ?? '0'
  return {
    year: Number(get('year')),
    month: Number(get('month')),
    day: Number(get('day')),
    hour: Number(get('hour')),
    minute: Number(get('minute')),
    second: Number(get('second')),
    weekday: WEEKDAY_INDEX[get('weekday')] ?? 0,
  }
}

function localHourDecimal(p) {
  return p.hour + p.minute / 60 + p.second / 3600
}

function isWeekendLocal(p) {
  return p.weekday === 0 || p.weekday === 6
}

function inWindow(hour, open, close) {
  return hour >= open && hour < close
}

function sessionStatus(def, now) {
  const parts = zonedParts(now, def.timeZone)
  if (isWeekendLocal(parts)) return 'closed'
  const h = localHourDecimal(parts)
  if (inWindow(h, def.openLocal, def.closeLocal)) return 'open'
  if (h < def.openLocal) return 'upcoming'
  return 'closed'
}

const tokyo = { timeZone: 'Asia/Tokyo', openLocal: 9, closeLocal: 18 }
const london = { timeZone: 'Europe/London', openLocal: 8, closeLocal: 17 }
const ny = { timeZone: 'America/New_York', openLocal: 9.5, closeLocal: 16 }

function assert(cond, msg) {
  if (!cond) throw new Error(msg)
}

function expectStatus(def, iso, expected, label) {
  const got = sessionStatus(def, new Date(iso))
  assert(got === expected, `${label}: expected ${expected}, got ${got} @ ${iso}`)
}

// --- Baseline (été) : même fenêtres qu’avant en UTC d’été ---
const wed8 = '2026-09-23T08:00:00Z'
expectStatus(london, wed8, 'open', 'london wed8')
expectStatus(tokyo, wed8, 'open', 'tokyo wed8')
expectStatus(ny, wed8, 'upcoming', 'ny wed8')

const wed18 = '2026-09-23T18:00:00Z'
expectStatus(london, wed18, 'closed', 'london wed18')
// 18:00 UTC = 03:00 JST jeudi → avant l’ouverture locale
expectStatus(tokyo, wed18, 'upcoming', 'tokyo wed18')
expectStatus(ny, wed18, 'open', 'ny wed18')

const sat = '2026-09-26T12:00:00Z'
expectStatus(london, sat, 'closed', 'london sat')
expectStatus(tokyo, sat, 'closed', 'tokyo sat')
expectStatus(ny, sat, 'closed', 'ny sat')

// --- Londres DST : fin le 2026-10-25 (BST → GMT) ---
// Même instant UTC 07:30 : ouvert en BST, à venir en GMT
expectStatus(london, '2026-10-23T07:30:00Z', 'open', 'london pre-DST 07:30Z')
expectStatus(london, '2026-10-26T07:30:00Z', 'upcoming', 'london post-DST 07:30Z')
// Mid-session explicite avant / après
expectStatus(london, '2026-10-23T10:00:00Z', 'open', 'london 2026-10-23 mid')
expectStatus(london, '2026-10-26T10:00:00Z', 'open', 'london 2026-10-26 mid')
expectStatus(london, '2026-10-23T16:30:00Z', 'closed', 'london 2026-10-23 after') // 17:30 BST
expectStatus(london, '2026-10-26T17:30:00Z', 'closed', 'london 2026-10-26 after') // 17:30 GMT

// --- New York DST : fin le 2026-11-01 (EDT → EST) ---
// Même instant UTC 14:00 : ouvert en EDT (10:00), à venir en EST (09:00)
expectStatus(ny, '2026-10-30T14:00:00Z', 'open', 'ny pre-DST 14:00Z')
expectStatus(ny, '2026-11-02T14:00:00Z', 'upcoming', 'ny post-DST 14:00Z')
expectStatus(ny, '2026-10-30T13:00:00Z', 'upcoming', 'ny 2026-10-30 before open')
expectStatus(ny, '2026-11-02T14:30:00Z', 'open', 'ny 2026-11-02 at open')
expectStatus(ny, '2026-10-30T20:30:00Z', 'closed', 'ny 2026-10-30 after')
expectStatus(ny, '2026-11-02T21:30:00Z', 'closed', 'ny 2026-11-02 after')

// --- Vendredi soir UTC ---
const friEve = '2026-10-23T21:00:00Z'
expectStatus(london, friEve, 'closed', 'london fri eve') // 22:00 BST
expectStatus(ny, friEve, 'closed', 'ny fri eve') // 17:00 EDT
expectStatus(tokyo, friEve, 'closed', 'tokyo fri eve') // samedi 06:00 JST (week-end local)

// --- Dimanche soir UTC ---
// Londres / NY encore dimanche → fermés ; Tokyo déjà lundi matin → à venir
const sunEve = '2026-10-25T21:00:00Z'
expectStatus(london, sunEve, 'closed', 'london sun eve')
expectStatus(ny, sunEve, 'closed', 'ny sun eve')
expectStatus(tokyo, sunEve, 'upcoming', 'tokyo sun eve → mon local')

console.log('SESSION_CHECKS_PASS', {
  wed8: { london: 'open', tokyo: 'open', ny: 'upcoming' },
  wed18: { london: 'closed', tokyo: 'upcoming', ny: 'open' },
  sat: 'all closed',
  londonDst: { '2026-10-23T07:30Z': 'open', '2026-10-26T07:30Z': 'upcoming' },
  nyDst: { '2026-10-30T14:00Z': 'open', '2026-11-02T14:00Z': 'upcoming' },
  friEve: { london: 'closed', ny: 'closed', tokyo: 'closed' },
  sunEve: { london: 'closed', ny: 'closed', tokyo: 'upcoming' },
})
