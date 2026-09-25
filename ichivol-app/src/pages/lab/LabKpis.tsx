import type { useLabController } from './useLabController'

type Ctrl = ReturnType<typeof useLabController>

export function LabKpis({ c }: { c: Ctrl }) {
  const { labKpis } = c
  return (
    <section className="iv-metrics bt-kpis" aria-label="Couverture Strategy Lab">
      {labKpis.map((kpi) => (
        <div key={kpi.label} className="iv-metric">
          <div className="iv-metric-label">{kpi.label}</div>
          <div className="iv-metric-value mono">
            {kpi.value ?? 'Non disponible'}
          </div>
          {kpi.meta ? <small>{kpi.meta}</small> : null}
        </div>
      ))}
    </section>
  )
}
