import type { PaperOverviewPosition } from '../../lib/paper'

export type ConcentrationSlice = { symbol: string; pct: number }

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
