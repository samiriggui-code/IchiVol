/** Shared Desk (Overview) formatters and constants. */

export const REFRESH_MS = 60_000
export const PRIMARY_SYMBOLS = [
  'BTCUSDT',
  'ETHUSDT',
  'SOLUSDT',
  'BNBUSDT',
  'XRPUSDT',
  'LINKUSDT',
]

export type EquityPeriod = '1J' | '1S' | '1M' | '3M'

/** Percentage already expressed as percent units (e.g. 58.5), not ratio. */
export function fmtPctPoints(
  v: number | null | undefined,
  digits = 1,
  signed = false,
): string {
  if (v == null || Number.isNaN(v)) return '—'
  const n = new Intl.NumberFormat('fr-FR', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
    signDisplay: signed ? 'exceptZero' : 'auto',
  }).format(v)
  return `${n} %`
}

/**
 * Part engagée du capital, en points (non plafonnée : 497 = 4,97× l'équité).
 * Au-delà de 100 %, le compte engage plus que son équité : on l'affiche avec le levier.
 */
export function fmtEngagedPct(v: number | null | undefined, digits = 1): string {
  if (v == null || !Number.isFinite(v)) return '—'
  const base = `${fmtPctPoints(v, digits)} du capital`
  if (v <= 100) return base
  const lev = new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v / 100)
  return `${base} · levier ${lev}x`
}

/** Vrai quand la part engagée dépasse l'équité (compte sur levier). */
export function isLeveraged(v: number | null | undefined): boolean {
  return v != null && Number.isFinite(v) && v > 100
}

/** Ratio 0–1 → pourcentage fr-FR (ex. 0.585 → « 58,5 % »). */
export function fmtPct(v: number | null | undefined, digits = 1, signed = true): string {
  if (v == null || Number.isNaN(v)) return '—'
  return fmtPctPoints(v * 100, digits, signed)
}

export function fmtDec(v: number | null | undefined, digits = 2): string {
  if (v == null || Number.isNaN(v)) return '—'
  return new Intl.NumberFormat('fr-FR', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(v)
}

export function fmtEur(v: number | null | undefined, digits = 0): string {
  if (v == null || Number.isNaN(v)) return '—'
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(v)
}

export function fmtPrice(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '—'
  if (v >= 1000) {
    return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 }).format(v)
  }
  if (v >= 1) {
    return new Intl.NumberFormat('fr-FR', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(v)
  }
  return new Intl.NumberFormat('fr-FR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 5,
  }).format(v)
}

export function fmtClock(iso: string): string {
  return new Date(iso).toLocaleTimeString('fr-FR', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}
