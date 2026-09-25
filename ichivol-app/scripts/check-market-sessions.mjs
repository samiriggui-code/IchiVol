/** Session status checks at two UTC hours (mirrors src/lib/marketSessions.ts). */
function utcHourDecimal(d) {
  return d.getUTCHours() + d.getUTCMinutes() / 60 + d.getUTCSeconds() / 3600
}
function isWeekendUtc(d) {
  const day = d.getUTCDay()
  return day === 0 || day === 6
}
function inWindow(hour, open, close) {
  return hour >= open && hour < close
}
function sessionStatus(def, now) {
  if (isWeekendUtc(now)) return 'closed'
  const h = utcHourDecimal(now)
  if (inWindow(h, def.openUtc, def.closeUtc)) return 'open'
  if (h < def.openUtc) return 'upcoming'
  return 'closed'
}

const london = { openUtc: 7, closeUtc: 16 }
const tokyo = { openUtc: 0, closeUtc: 9 }
const ny = { openUtc: 13.5, closeUtc: 20 }

function assert(cond, msg) {
  if (!cond) throw new Error(msg)
}

const wed8 = new Date('2026-09-23T08:00:00Z')
assert(sessionStatus(london, wed8) === 'open', 'london wed8')
assert(sessionStatus(tokyo, wed8) === 'open', 'tokyo wed8')
assert(sessionStatus(ny, wed8) === 'upcoming', 'ny wed8')

const wed18 = new Date('2026-09-23T18:00:00Z')
assert(sessionStatus(london, wed18) === 'closed', 'london wed18')
assert(sessionStatus(tokyo, wed18) === 'closed', 'tokyo wed18')
assert(sessionStatus(ny, wed18) === 'open', 'ny wed18')

const sat = new Date('2026-09-26T12:00:00Z')
assert(sessionStatus(london, sat) === 'closed', 'london sat')

console.log('SESSION_CHECKS_PASS', {
  wed8: { london: 'open', tokyo: 'open', ny: 'upcoming' },
  wed18: { london: 'closed', tokyo: 'closed', ny: 'open' },
  sat: 'all closed',
})
