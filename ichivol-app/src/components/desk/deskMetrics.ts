import type { PaperOverview, PaperOverviewPosition } from '../../lib/paper'

export type ConcentrationSlice = { symbol: string; pct: number }

/** Snapshot Desk d’un livre paper (tous les portefeuilles virtuels). */
export type DeskBookSnapshot = {
  code: string
  label: string
  equity: number
  cash: number
  day_change: number | null
  open_risk_amount: number
  open_risk_pct: number | null
  max_open_risk_pct: number | null
  open_positions: number
  capital: number
}

export type DeskBooksAggregate = {
  books: DeskBookSnapshot[]
  equity: number
  cash: number
  day_change: number | null
  open_risk_amount: number
  open_risk_pct: number | null
  max_open_risk_pct: number | null
  open_positions: number
  book_count: number
}

export function snapshotFromOverview(
  code: string,
  label: string,
  ov: PaperOverview,
): DeskBookSnapshot {
  const acct = ov.account
  const risk = ov.risk
  return {
    code,
    label,
    equity: acct?.equity ?? 0,
    cash: acct?.cash ?? 0,
    day_change: acct?.day_change ?? null,
    open_risk_amount: risk?.open_risk_amount ?? 0,
    open_risk_pct: risk?.open_risk_pct ?? null,
    max_open_risk_pct: risk?.max_open_risk_pct ?? null,
    open_positions: risk?.open_positions ?? acct?.open_positions ?? 0,
    capital: risk?.capital ?? acct?.equity ?? 0,
  }
}

/** Agrège tous les livres paper pour les 4 métriques Desk. */
export function aggregateDeskBooks(books: DeskBookSnapshot[]): DeskBooksAggregate {
  if (books.length === 0) {
    return {
      books: [],
      equity: 0,
      cash: 0,
      day_change: null,
      open_risk_amount: 0,
      open_risk_pct: null,
      max_open_risk_pct: null,
      open_positions: 0,
      book_count: 0,
    }
  }
  const equity = books.reduce((s, b) => s + b.equity, 0)
  const cash = books.reduce((s, b) => s + b.cash, 0)
  const anyDay = books.some((b) => b.day_change != null)
  const day_change = anyDay
    ? books.reduce((s, b) => s + (b.day_change ?? 0), 0)
    : null
  const open_risk_amount = books.reduce((s, b) => s + b.open_risk_amount, 0)
  const capital = books.reduce((s, b) => s + Math.max(0, b.capital || b.equity), 0)
  const open_risk_pct = capital > 0 ? open_risk_amount / capital : null
  // Global cap = each book's cap in euros, summed, over total capital (not the largest per-book %).
  const capEur = books.reduce(
    (s, b) =>
      s + (b.max_open_risk_pct != null && Number.isFinite(b.max_open_risk_pct) ? b.max_open_risk_pct * Math.max(0, b.capital || b.equity) : 0),
    0,
  )
  const max_open_risk_pct = capital > 0 && capEur > 0 ? capEur / capital : null
  const open_positions = books.reduce((s, b) => s + b.open_positions, 0)
  return {
    books,
    equity,
    cash,
    day_change,
    open_risk_amount,
    open_risk_pct,
    max_open_risk_pct,
    open_positions,
    book_count: books.length,
  }
}

/** % notional par symbole parmi les positions valorisées. */
export function concentrationFromPositions(
  positions: PaperOverviewPosition[],
): ConcentrationSlice[] {
  const values = positions
    .map((p) => ({
      symbol: p.symbol.replace(/USDT$/i, ''),
      mv: Math.abs(
        // Without a fresh mark, fall back to the notional engaged at entry (else an open lot shows as « aucune position »).
        p.market_value ?? (p.current_price != null ? p.current_price * (p.qty ?? 0) : (p.notional ?? 0)),
      ),
    }))
    .filter((p) => p.mv > 0)
  // Same symbol held by several portfolios counts once, with the sum of its lots.
  const bySymbol = new Map<string, number>()
  for (const v of values) bySymbol.set(v.symbol, (bySymbol.get(v.symbol) ?? 0) + v.mv)
  const total = values.reduce((s, v) => s + v.mv, 0)
  if (total <= 0) return []
  return [...bySymbol]
    .map(([symbol, mv]) => ({ symbol, pct: (mv / total) * 100 }))
    .sort((a, b) => b.pct - a.pct)
}

/**
 * Drawdown front : (peak equity_curve − equity actuelle) / peak.
 * Retourne un ratio ≤ 0 (ex. −0.039) ou null si données insuffisantes.
 */
export function drawdownFromCurve(
  curve: { equity: number }[],
  equity: number | null | undefined,
): number | null {
  if (equity == null || !Number.isFinite(equity) || curve.length === 0) return null
  let peak = equity
  for (const p of curve) {
    if (Number.isFinite(p.equity) && p.equity > peak) peak = p.equity
  }
  if (peak <= 0) return null
  return (equity - peak) / peak
}
