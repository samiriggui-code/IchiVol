import type { PaperOverviewPosition } from '../../lib/paper'

export const RING_COLORS = ['#548f87', '#8c9eb4', '#c2b596', '#a9bdb2', '#7d8288'] as const

export type ConcentrationSlice = { symbol: string; pct: number }

/** % notional par symbole parmi les positions valorisées. */
export function concentrationFromPositions(
  positions: PaperOverviewPosition[],
): ConcentrationSlice[] {
  const values = positions
    .map((p) => ({
      symbol: p.symbol.replace(/USDT$/i, ''),
      mv: Math.abs(
        p.market_value ?? (p.current_price != null ? p.current_price * (p.qty ?? 0) : 0),
      ),
    }))
    .filter((p) => p.mv > 0)
  const total = values.reduce((s, v) => s + v.mv, 0)
  if (total <= 0) return []
  return values
    .map((v) => ({ symbol: v.symbol, pct: (v.mv / total) * 100 }))
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
