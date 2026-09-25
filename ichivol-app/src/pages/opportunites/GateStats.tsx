export function GateStats({
  loading,
  empty,
  buy,
  sell,
  watch,
  total,
  timeframe,
  onFilterBuySell,
  onClearActionable,
}: {
  loading: boolean
  empty: boolean
  buy: number
  sell: number
  watch: number
  total: number
  timeframe: string
  onFilterBuySell: () => void
  onClearActionable: () => void
}) {
  const dash = loading && empty
  return (
    <section className="dec-gate-stats" aria-label="Résumé Portes">
      <button
        type="button"
        className="panel overview-stat overview-stat--bull"
        onClick={onFilterBuySell}
        title="Filtrer les actionnables Achat"
      >
        <span className="overview-stat-label muted">Achats (Portes)</span>
        <strong className="mono">{dash ? '—' : buy}</strong>
      </button>
      <button
        type="button"
        className="panel overview-stat overview-stat--bear"
        onClick={onFilterBuySell}
        title="Filtrer les actionnables Vente"
      >
        <span className="overview-stat-label muted">Ventes (Portes)</span>
        <strong className="mono">{dash ? '—' : sell}</strong>
      </button>
      <button type="button" className="panel overview-stat" onClick={onClearActionable}>
        <span className="overview-stat-label muted">Surveillance</span>
        <strong className="mono">{dash ? '—' : watch}</strong>
      </button>
      <div className="panel overview-stat">
        <span className="overview-stat-label muted">Scannées · {timeframe}</span>
        <strong className="mono">{dash ? '—' : total}</strong>
        <span className="overview-stat-meta muted">{buy + sell} actionnables</span>
      </div>
    </section>
  )
}
