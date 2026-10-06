/**
 * Desk : les trois portefeuilles paper vus ensemble (capital additionné, courbes côte à côte).
 * Fonctions pures, sans appel réseau, pour pouvoir les tester.
 */

import type { PaperOverview, PaperOverviewPosition } from './paper.ts'

export type DeskPortfolio = { code: string; label: string; color: string; hint: string }

export const DESK_PORTFOLIOS: readonly DeskPortfolio[] = [
  {
    code: 'ICHIVOL_BASELINE_V1',
    label: 'IchiVol',
    color: '#478f83',
    hint: 'Règles IchiVol, décision chaque heure (référence figée)',
  },
  {
    code: 'ICHIVOL_SESSIONS_V1',
    label: 'Sessions',
    color: '#5b7fb8',
    hint: 'Mêmes règles, décisions aux ouvertures et clôtures de Tokyo, Londres et New York',
  },
  {
    code: 'RS_D1_PAPER_V1',
    label: 'RS-D1',
    color: '#c0873a',
    hint: 'Cassure Donchian 4h, pilotée par sa seule règle',
  },
] as const

export function deskPortfolio(code: string | null | undefined): DeskPortfolio | undefined {
  return DESK_PORTFOLIOS.find((p) => p.code === code)
}

export type DeskAccount = {
  initial_cash: number
  cash: number
  invested: number
  equity: number
  day_change: number | null
  open_positions: number
  /** Nombre de portefeuilles réellement additionnés (ceux qui ont répondu). */
  portfolios: number
}

/** Additionne les comptes des portefeuilles qui ont répondu ; null si aucun. */
export function sumAccounts(overviews: Array<PaperOverview | null>): DeskAccount | null {
  const ok = overviews.filter((o): o is PaperOverview => o?.account != null)
  if (ok.length === 0) return null
  const days = ok.map((o) => o.account.day_change).filter((d): d is number => d != null && Number.isFinite(d))
  return {
    initial_cash: ok.reduce((s, o) => s + (o.account.initial_cash || 0), 0),
    cash: ok.reduce((s, o) => s + (o.account.cash || 0), 0),
    invested: ok.reduce((s, o) => s + (o.account.invested || 0), 0),
    equity: ok.reduce((s, o) => s + (o.account.equity || 0), 0),
    day_change: days.length ? days.reduce((s, d) => s + d, 0) : null,
    open_positions: ok.reduce((s, o) => s + (o.account.open_positions || 0), 0),
    portfolios: ok.length,
  }
}

export type DeskRisk = {
  open_risk_amount: number
  capital: number
  open_risk_pct: number | null
  max_open_risk_pct: number | null
  open_positions: number
  max_open_positions: number
}

/** Risque ouvert total rapporté au capital total ; limite = la plus stricte des limites. */
export function sumRisk(overviews: Array<PaperOverview | null>): DeskRisk | null {
  const risks = overviews.map((o) => o?.risk).filter((r): r is NonNullable<PaperOverview['risk']> => r != null)
  if (risks.length === 0) return null
  const capital = risks.reduce((s, r) => s + (r.capital || 0), 0)
  const amount = risks.reduce((s, r) => s + (r.open_risk_amount || 0), 0)
  const limits = risks.map((r) => r.max_open_risk_pct).filter((v): v is number => v != null && Number.isFinite(v))
  return {
    open_risk_amount: amount,
    capital,
    open_risk_pct: capital > 0 ? amount / capital : null,
    max_open_risk_pct: limits.length ? Math.min(...limits) : null,
    open_positions: risks.reduce((s, r) => s + (r.open_positions || 0), 0),
    max_open_positions: risks.reduce((s, r) => s + (r.max_open_positions || 0), 0),
  }
}

export type DeskPosition = PaperOverviewPosition & { portfolio_code: string }

/** Toutes les positions ouvertes, chacune étiquetée avec son portefeuille, la plus grosse d'abord. */
export function mergePositions(
  overviews: Array<{ code: string; overview: PaperOverview | null }>,
): DeskPosition[] {
  const out: DeskPosition[] = []
  for (const { code, overview } of overviews) {
    for (const p of overview?.positions ?? []) out.push({ ...p, portfolio_code: code })
  }
  const value = (p: PaperOverviewPosition) =>
    Math.abs(p.market_value ?? (p.current_price != null ? p.current_price * (p.qty ?? 0) : p.notional ?? 0))
  return out.sort((a, b) => value(b) - value(a))
}

export type CurvePoint = { ms: number; equity: number }

/**
 * Courbe du total : à chaque instant où au moins une courbe bouge, somme des dernières valeurs connues.
 * Ne commence que lorsque toutes les courbes ont un premier point (sinon le total ferait un saut).
 */
export function sumCurves(series: CurvePoint[][]): CurvePoint[] {
  const live = series.filter((s) => s.length > 0)
  if (live.length === 0) return []
  const start = Math.max(...live.map((s) => s[0]!.ms))
  const times = [...new Set(live.flatMap((s) => s.map((p) => p.ms)))].filter((t) => t >= start).sort((a, b) => a - b)
  const idx = live.map(() => 0)
  const out: CurvePoint[] = []
  for (const t of times) {
    let total = 0
    live.forEach((s, k) => {
      while (idx[k]! + 1 < s.length && s[idx[k]! + 1]!.ms <= t) idx[k]!++
      total += s[idx[k]!]!.equity
    })
    out.push({ ms: t, equity: total })
  }
  return out
}

/** Baisse depuis le plus haut de la courbe, en ratio ≤ 0 ; null si la courbe est vide. */
export function drawdownOf(curve: CurvePoint[]): number | null {
  if (curve.length === 0) return null
  let peak = curve[0]!.equity
  for (const p of curve) peak = Math.max(peak, p.equity)
  const last = curve[curve.length - 1]!.equity
  return peak > 0 ? (last - peak) / peak : null
}

/** Part de chaque actif dans l'exposition totale, positions du même actif additionnées. */
export function concentrationBySymbol(positions: PaperOverviewPosition[]): { symbol: string; pct: number }[] {
  const by = new Map<string, number>()
  for (const p of positions) {
    const mv = Math.abs(p.market_value ?? (p.current_price != null ? p.current_price * (p.qty ?? 0) : 0))
    if (!(mv > 0)) continue
    const sym = p.symbol.replace(/USDT$/i, '')
    by.set(sym, (by.get(sym) ?? 0) + mv)
  }
  const total = [...by.values()].reduce((s, v) => s + v, 0)
  if (total <= 0) return []
  return [...by.entries()].map(([symbol, mv]) => ({ symbol, pct: (mv / total) * 100 })).sort((a, b) => b.pct - a.pct)
}
