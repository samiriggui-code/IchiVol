import type { ReactNode } from 'react'
import { workspaceEyebrow, workspacePageMeta } from '../lib/workspaceNav'

/** Tag tone matching maquette `badge()` heuristic. */
export type TagTone = 'green' | 'amber' | 'red' | 'gray' | ''

export function tagToneFromLabel(label: string, explicit?: TagTone): TagTone {
  if (explicit !== undefined) return explicit
  if (/PASSE|ACCEPTÉ|OUVERTE|VALIDÉ/i.test(label)) return 'green'
  if (/REFUS|BLOQU|ERREUR/i.test(label)) return 'red'
  if (/PRUDENCE|TRIGGERED/i.test(label)) return 'amber'
  return ''
}

export function Tag({
  children,
  tone,
}: {
  children: ReactNode
  tone?: TagTone
}) {
  const label = typeof children === 'string' ? children : ''
  const resolved = tagToneFromLabel(label, tone)
  return <span className={resolved ? `tag ${resolved}` : 'tag'}>{children}</span>
}

/** Page chrome: eyebrow / h1 / subtitle — exact maquette structure. */
export function WorkspacePageHead({
  path,
  actions,
  subtitleExtra,
}: {
  path: string
  actions?: ReactNode
  /** Appended after META.subtitle (e.g. filter note). */
  subtitleExtra?: ReactNode
}) {
  const meta = workspacePageMeta(path)
  const title = meta?.label ?? 'IchiVol'
  const subtitle = meta?.subtitle ?? ''
  return (
    <div className="page-head">
      <div>
        <div className="eyebrow">{workspaceEyebrow(path)}</div>
        <h1>{title}</h1>
        <p className="subtitle">
          {subtitle}
          {subtitleExtra}
        </p>
      </div>
      {actions != null ? <div className="actions">{actions}</div> : null}
    </div>
  )
}

export function Metric({
  label,
  value,
  hint,
  featured,
  tone,
}: {
  label: string
  value: ReactNode
  hint: ReactNode
  featured?: boolean
  tone?: 'up' | 'down' | ''
}) {
  const cls = ['metric', featured ? 'featured' : '', tone ?? ''].filter(Boolean).join(' ')
  return (
    <div className={cls}>
      <div className="metric-label">
        {label}
        <span aria-hidden>↗</span>
      </div>
      <div className="metric-value">{value}</div>
      <small>{hint}</small>
    </div>
  )
}

export function StatLine({ label, value }: { label: ReactNode; value: ReactNode }) {
  return (
    <div className="statline">
      <span>{label}</span>
      <b>{value}</b>
    </div>
  )
}

export function RiskTrack({
  label,
  value,
  pct,
  warn,
}: {
  label: string
  value: string
  pct: number
  warn?: boolean
}) {
  const width = Math.max(0, Math.min(100, pct))
  return (
    <>
      <div className="risk-row">
        <span>{label}</span>
        <span className={`mono${warn ? ' warn' : ''}`}>{value}</span>
      </div>
      <div className="track" aria-hidden>
        <span style={{ width: `${width}%`, ...(warn ? { background: '#b99557' } : {}) }} />
      </div>
    </>
  )
}

export function Card({
  title,
  extra,
  children,
  className = '',
  bodyClassName,
}: {
  title?: ReactNode
  extra?: ReactNode
  children: ReactNode
  className?: string
  /** When set, wraps children in card-body; omit if children already include table-wrap / custom layout. */
  bodyClassName?: string | false
}) {
  const cls = ['card', className].filter(Boolean).join(' ')
  return (
    <section className={cls}>
      {title != null && (
        <div className="card-head">
          <h2>{title}</h2>
          {extra}
        </div>
      )}
      {bodyClassName === false ? (
        children
      ) : (
        <div className={bodyClassName ?? 'card-body'}>{children}</div>
      )}
    </section>
  )
}
