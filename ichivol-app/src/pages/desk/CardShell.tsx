import type { ReactNode } from 'react'

export function CardShell({
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
