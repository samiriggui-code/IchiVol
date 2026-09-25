import type { ReactNode } from 'react'
import type { PaperOverviewPosition } from '../../lib/paper'
import './DeskRings.css'

export const RING_COLORS = ['#548f87', '#8c9eb4', '#c2b596', '#a9bdb2', '#7d8288'] as const

export function DeskRing({
  parts,
  center,
  label,
}: {
  parts: { pct: number; color: string }[]
  center: string
  label: string
}) {
  const offsets: number[] = []
  let acc = 0
  for (const p of parts) {
    offsets.push(acc)
    acc += p.pct
  }
  return (
    <div className="desk-ring">
      <svg viewBox="0 0 200 200" role="img" aria-label={`${label} : ${center}`}>
        <circle cx="100" cy="100" r="80" fill="none" stroke="var(--line, var(--border))" strokeWidth="19" />
        {parts.map((p, i) => (
          <circle
            key={i}
            cx="100"
            cy="100"
            r="80"
            pathLength="100"
            fill="none"
            stroke={p.color}
            strokeWidth="19"
            strokeDasharray={`${p.pct} ${100 - p.pct}`}
            strokeDashoffset={-offsets[i]}
            transform="rotate(-90 100 100)"
          />
        ))}
      </svg>
      <div>
        <b>{center}</b>
        <small>{label}</small>
      </div>
    </div>
  )
}

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

export function DeskCardShell({
  title,
  meta,
  children,
  className,
  footer,
}: {
  title: string
  meta?: ReactNode
  children: ReactNode
  className?: string
  footer?: ReactNode
}) {
  return (
    <section className={`panel desk-card ${className ?? ''}`.trim()}>
      <header className="panel-head">
        <h2>{title}</h2>
        {meta ? <span className="panel-meta">{meta}</span> : null}
      </header>
      <div className="card-body">{children}</div>
      {footer ? <div className="card-foot">{footer}</div> : null}
    </section>
  )
}
