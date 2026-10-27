/**
 * Heure des graphiques : les bougies arrivent en temps universel (UTC) ; lightweight-charts les affiche en UTC
 * par défaut, donc 1 h (hiver) ou 2 h (été) de moins qu'à Paris. Ces formateurs affichent l'heure de Paris
 * (changements d'heure compris) sur l'axe et dans le réticule.
 */
import type { Time } from 'lightweight-charts'

export const CHART_TIME_ZONE = 'Europe/Paris'

function toDate(time: Time): Date | null {
  if (typeof time === 'number') return new Date(time * 1000)
  if (typeof time === 'string') {
    const ms = Date.parse(time)
    return Number.isNaN(ms) ? null : new Date(ms)
  }
  if (time && typeof time === 'object' && 'year' in time) {
    return new Date(Date.UTC(time.year, time.month - 1, time.day))
  }
  return null
}

const fmt = (opts: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat('fr-FR', { timeZone: CHART_TIME_ZONE, ...opts })
const FULL = fmt({ day: '2-digit', month: 'short', year: '2-digit', hour: '2-digit', minute: '2-digit' })
const YEAR = fmt({ year: 'numeric' })
const MONTH = fmt({ month: 'short' })
const DAY = fmt({ day: 'numeric', month: 'short' })
const HOUR = fmt({ hour: '2-digit', minute: '2-digit' })
const SECONDS = fmt({ hour: '2-digit', minute: '2-digit', second: '2-digit' })

/** Réticule : date et heure de Paris. */
export function parisTimeFormatter(time: Time): string {
  const d = toDate(time)
  return d ? FULL.format(d) : ''
}

/** Graduations de l'axe (TickMarkType : 0 année, 1 mois, 2 jour, 3 heure, 4 heure avec secondes). */
export function parisTickMarkFormatter(time: Time, tickMarkType: number): string {
  const d = toDate(time)
  if (!d) return ''
  switch (tickMarkType) {
    case 0:
      return YEAR.format(d)
    case 1:
      return MONTH.format(d)
    case 2:
      return DAY.format(d)
    case 4:
      return SECONDS.format(d)
    default:
      return HOUR.format(d)
  }
}
