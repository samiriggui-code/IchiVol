import { CardShell } from './CardShell'
import { BASELINE, type EquityPeriod } from './deskFormat'

function filterEquityCurve(
  points: { t: string; equity: number }[],
  period: EquityPeriod,
  now = Date.now(),
): { t: string; equity: number }[] {
  const ms =
    period === '1J'
      ? 86_400_000
      : period === '1S'
        ? 7 * 86_400_000
        : period === '1M'
          ? 30 * 86_400_000
          : 90 * 86_400_000
  const cutoff = now - ms
  return points.filter((p) => {
    const t = Date.parse(p.t)
    return !Number.isNaN(t) && t >= cutoff
  })
}

function EquityChart({
  points,
  initial,
  period,
  onPeriod,
}: {
  points: { t: string; equity: number }[]
  initial: number
  period: EquityPeriod
  onPeriod: (p: EquityPeriod) => void
}) {
  const filtered = filterEquityCurve(points, period)
  return (
    <div className="desk-equity">
      <div className="desk-equity-periods" role="group" aria-label="Période">
        {(['1J', '1S', '1M', '3M'] as const).map((p) => (
          <button
            key={p}
            type="button"
            className={period === p ? 'is-active' : undefined}
            onClick={() => onPeriod(p)}
          >
            {p}
          </button>
        ))}
      </div>
      {filtered.length < 2 ? (
        <div className="ov-spark ov-spark--empty muted">Courbe en construction</div>
      ) : (
        (() => {
          const vals = filtered.map((p) => p.equity)
          const min = Math.min(...vals, initial)
          const max = Math.max(...vals, initial)
          const span = Math.max(1e-6, max - min)
          const w = 640
          const h = 160
          const poly = vals
            .map((v, i) => {
              const x = (i / (vals.length - 1)) * w
              const y = h - ((v - min) / span) * (h - 8) - 4
              return `${x.toFixed(1)},${y.toFixed(1)}`
            })
            .join(' ')
          const up = vals[vals.length - 1] >= initial
          return (
            <svg
              className={`desk-equity-svg ${up ? 'is-up' : 'is-down'}`}
              viewBox={`0 0 ${w} ${h}`}
              role="img"
              aria-label={`Trajectoire equity ${period}`}
            >
              <polyline fill="none" strokeWidth="2" points={poly} />
            </svg>
          )
        })()
      )}
    </div>
  )
}

export function EquitySection({
  ovError,
  points,
  initial,
  period,
  onPeriod,
}: {
  ovError: string | null
  points: { t: string; equity: number }[]
  initial: number
  period: EquityPeriod
  onPeriod: (p: EquityPeriod) => void
}) {
  return (
    <CardShell title="Trajectoire du portefeuille" meta={BASELINE}>
      {ovError ? (
        <p className="muted">{ovError}</p>
      ) : (
        <EquityChart points={points} initial={initial} period={period} onPeriod={onPeriod} />
      )}
    </CardShell>
  )
}
