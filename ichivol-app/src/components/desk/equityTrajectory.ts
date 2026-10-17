/**
 * Trajectoire des portefeuilles (Desk) : calculs purs, sans React.
 * Chaque livre est ramené en % de son capital de départ pour partager un seul axe ;
 * ses ordres deviennent des repères (achat, vente à découvert, clôture) et des périodes de maintien.
 */

import type { EquityPeriod } from '../../pages/desk/deskFormat'

/** Palette catégorielle validée (dataviz, fond #fefdfb) : un livre garde toujours sa couleur. */
export const BOOK_PALETTE = [
  '#2a78d6',
  '#eb6834',
  '#1baf7a',
  '#eda100',
  '#e87ba4',
  '#008300',
  '#6250d6',
  '#e34948',
] as const

const BOOK_SLOT: Record<string, number> = {
  ICHIVOL_BASELINE_V1: 0,
  ICHIVOL_SESSIONS_V1: 1,
  FUTURES_CRYPTO_V1: 2,
  ICHIVOL_SHORTS_V1: 3,
  ICHIVOL_4H_V1: 4,
  ICHIVOL_WIDE_V1: 5,
  RS_D1_PAPER_V1: 6,
}

/** Couleur d'un livre : fixée par son code (un filtre ne repeint jamais les autres), sinon le premier emplacement libre. */
export function bookColors(codes: string[]): Record<string, string> {
  const out: Record<string, string> = {}
  const used = new Set<number>()
  for (const c of codes) {
    const slot = BOOK_SLOT[c]
    if (slot != null) {
      out[c] = BOOK_PALETTE[slot]!
      used.add(slot)
    }
  }
  let next = 0
  for (const c of codes) {
    if (out[c]) continue
    while (used.has(next) && next < BOOK_PALETTE.length - 1) next += 1
    out[c] = BOOK_PALETTE[next]!
    used.add(next)
  }
  return out
}

export function periodCutoffMs(period: EquityPeriod, now = Date.now()): number {
  const day = 86_400_000
  const ms = period === '1J' ? day : period === '1S' ? 7 * day : period === '1M' ? 30 * day : 90 * day
  return now - ms
}

/** Snapshots corrompus (79 M€…) : marche point à point autour de la médiane du compte. */
export function cleanEquitySeries(points: { t: string; equity: number }[]): { ms: number; equity: number }[] {
  const raw = points
    .map((p) => ({ ms: Date.parse(p.t), equity: p.equity }))
    .filter((p) => !Number.isNaN(p.ms) && Number.isFinite(p.equity) && p.equity > 0)
    .sort((a, b) => a.ms - b.ms)
  if (raw.length === 0) return []

  const sorted = [...raw.map((p) => p.equity)].sort((a, b) => a - b)
  const mid = sorted[Math.floor(sorted.length / 2)] ?? 5000
  const lo = mid * 0.9
  const hi = mid * 1.12

  const out: { ms: number; equity: number }[] = []
  for (const p of raw) {
    if (p.equity < lo || p.equity > hi) continue
    const prev = out[out.length - 1]
    if (prev) {
      if (p.ms === prev.ms) {
        out[out.length - 1] = p
        continue
      }
      const jump = Math.abs(p.equity - prev.equity)
      if (jump > Math.max(120, prev.equity * 0.04)) continue
    }
    out.push(p)
  }
  return out.length >= 2 ? out : raw.filter((p) => p.equity >= lo && p.equity <= hi)
}

export type PctPoint = { ms: number; equity: number; pct: number }

/**
 * Courbe d'un livre en % de son capital de départ, limitée à la période. La dernière valeur connue avant la
 * période ouvre la courbe, pour qu'un livre calme sur « 1J » reste visible au lieu de disparaître.
 */
export function buildPctSeries(
  points: { t: string; equity: number }[],
  initialCash: number | null | undefined,
  cutoffMs: number,
): PctPoint[] {
  const clean = cleanEquitySeries(points)
  if (clean.length === 0) return []
  const base = initialCash != null && initialCash > 0 ? initialCash : clean[0]!.equity
  const toPct = (p: { ms: number; equity: number }): PctPoint => ({ ...p, pct: p.equity / base - 1 })
  const inside = clean.filter((p) => p.ms >= cutoffMs)
  const before = [...clean].reverse().find((p) => p.ms < cutoffMs)
  const out = inside.map(toPct)
  if (before && (out.length === 0 || out[0]!.ms > cutoffMs)) out.unshift(toPct({ ms: cutoffMs, equity: before.equity }))
  return out
}

/** Dernière valeur connue à `ms` (null avant le premier point : le livre n'existait pas encore). */
export function valueAt(series: PctPoint[], ms: number): PctPoint | null {
  let found: PctPoint | null = null
  for (const p of series) {
    if (p.ms > ms) break
    found = p
  }
  return found
}

/** Valeur interpolée, pour poser un repère exactement sur le tracé. */
export function lerpPctAt(series: PctPoint[], ms: number): number | null {
  if (series.length === 0) return null
  if (ms <= series[0]!.ms) return series[0]!.pct
  for (let i = 1; i < series.length; i++) {
    const b = series[i]!
    if (ms <= b.ms) {
      const a = series[i - 1]!
      const r = (ms - a.ms) / Math.max(1, b.ms - a.ms)
      return a.pct + r * (b.pct - a.pct)
    }
  }
  return series[series.length - 1]!.pct
}

export type TradeOrder = {
  id: string
  position_id: string | null
  time: string
  symbol: string
  side: string
  filled_price: number
  qty: number
  notional: number
  fee: number
  reason: string | null
  book_code?: string
  book_label?: string
}

export type TradeMarkKind = 'entry_long' | 'entry_short' | 'exit'

export type TradeMark = {
  id: string
  bookCode: string
  bookLabel: string
  ms: number
  kind: TradeMarkKind
  symbol: string
  qty: number
  price: number
  notional: number
  fee: number
  reason: string | null
  /** Pour une clôture : sens de la position fermée et résultat brut estimé (prix de sortie − prix d'entrée). */
  closedSide?: 'long' | 'short'
  grossPnl?: number
}

export type HeldPosition = {
  bookCode: string
  symbol: string
  side: 'long' | 'short'
  openMs: number | null
  closeMs: number | null
}

function isBuy(side: string): boolean {
  return String(side).toUpperCase() === 'BUY'
}

/** Le moteur marque ses ordres d'entrée « open » (et « reinforce » pour un renfort) ; tout le reste ferme. */
function isEntryOrder(o: TradeOrder): boolean {
  const r = (o.reason ?? '').trim().toLowerCase()
  return r === 'open' || r === 'reinforce'
}

/**
 * Ordres → repères et positions tenues. Un ordre d'entrée BUY ouvre un achat, SELL une vente à découvert ;
 * un ordre de sortie SELL ferme un achat, BUY ferme une vente à découvert.
 */
export function buildTrades(
  orders: TradeOrder[],
  openNow: Array<{ bookCode: string; symbol: string }> = [],
): { marks: TradeMark[]; positions: HeldPosition[] } {
  const sorted = orders
    .map((o) => ({ o, ms: Date.parse(o.time) }))
    .filter((x) => Number.isFinite(x.ms))
    .sort((a, b) => a.ms - b.ms)

  const marks: TradeMark[] = []
  const byPosition = new Map<string, HeldPosition & { entryPrice: number | null }>()
  const positions: HeldPosition[] = []
  for (const { o, ms } of sorted) {
    const book = o.book_code ?? ''
    const key = `${book}|${o.position_id ?? `${o.symbol}`}`
    if (isEntryOrder(o)) {
      const side: 'long' | 'short' = isBuy(o.side) ? 'long' : 'short'
      marks.push(toMark(o, ms, side === 'long' ? 'entry_long' : 'entry_short'))
      const known = byPosition.get(key)
      if (!known || known.closeMs != null) {
        const pos = { bookCode: book, symbol: o.symbol, side, openMs: ms, closeMs: null, entryPrice: o.filled_price || null }
        byPosition.set(key, pos)
        positions.push(pos)
      }
      continue
    }
    const side: 'long' | 'short' = isBuy(o.side) ? 'short' : 'long'
    const m = toMark(o, ms, 'exit')
    m.closedSide = side
    let pos = byPosition.get(key)
    if (!pos) {
      // Ouverture plus ancienne que l'historique chargé : la position était déjà tenue au début du graphique.
      pos = { bookCode: book, symbol: o.symbol, side, openMs: null, closeMs: null, entryPrice: null }
      byPosition.set(key, pos)
      positions.push(pos)
    }
    if (pos.entryPrice && o.filled_price > 0) {
      m.grossPnl = (side === 'long' ? 1 : -1) * (o.filled_price - pos.entryPrice) * o.qty
    }
    pos.closeMs = ms
    marks.push(m)
  }
  // Une sortie partielle ne ferme pas une position encore ouverte aujourd'hui.
  for (const n of openNow) {
    const latest = [...positions].reverse().find((p) => p.bookCode === n.bookCode && p.symbol === n.symbol)
    if (latest) latest.closeMs = null
  }
  return { marks, positions: positions.map(({ bookCode, symbol, side, openMs, closeMs }) => ({ bookCode, symbol, side, openMs, closeMs })) }
}

function toMark(o: TradeOrder, ms: number, kind: TradeMarkKind): TradeMark {
  return {
    id: `${o.book_code ?? ''}-${o.id}`,
    bookCode: o.book_code ?? '',
    bookLabel: o.book_label ?? o.book_code ?? '',
    ms,
    kind,
    symbol: o.symbol,
    qty: o.qty,
    price: o.filled_price,
    notional: o.notional,
    fee: o.fee,
    reason: o.reason?.trim() || null,
  }
}

/** Positions qu'un livre tenait à `ms` (son « maintien »). */
export function heldAt(positions: HeldPosition[], bookCode: string, ms: number): HeldPosition[] {
  return positions.filter(
    (p) => p.bookCode === bookCode && (p.openMs == null || p.openMs <= ms) && (p.closeMs == null || p.closeMs > ms),
  )
}

/** Axe en % qui contient toujours 0 % (le capital de départ), 4 à 6 graduations rondes. */
export function pctAxis(lo: number, hi: number): { min: number; max: number; step: number; ticks: number[] } {
  const a = Math.min(lo, 0)
  const b = Math.max(hi, 0)
  const span = Math.max(b - a, 0.002)
  const steps = [0.0005, 0.001, 0.002, 0.0025, 0.005, 0.01, 0.02, 0.025, 0.05, 0.1, 0.2, 0.25, 0.5, 1]
  const step = steps.find((s) => span / s <= 5) ?? 1
  let min = Math.floor(a / step - 1e-9) * step
  let max = Math.ceil(b / step + 1e-9) * step
  // Un peu d'air pour que la courbe ne colle pas au bord.
  if (b - max > -step * 0.15) max += step
  if (a - min < step * 0.15) min -= step
  const ticks: number[] = []
  for (let v = max; v >= min - step / 2; v -= step) ticks.push(Math.abs(v) < 1e-12 ? 0 : v)
  return { min, max, step, ticks }
}

/** « +1,25 % », « −0,4 % », « 0 % ». */
export function fmtSignedPct(v: number, digits = 2): string {
  const n = Math.abs(v * 100)
  const txt = n.toLocaleString('fr-FR', { minimumFractionDigits: 0, maximumFractionDigits: digits })
  if (txt === '0' || n === 0) return '0 %'
  return `${v > 0 ? '+' : '−'}${txt} %`
}
