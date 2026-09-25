import type { ReactNode } from 'react'
import './DeskRings.css'
export {
  RING_COLORS,
  concentrationFromPositions,
  drawdownFromCurve,
  type ConcentrationSlice,
} from './deskMetrics'

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
