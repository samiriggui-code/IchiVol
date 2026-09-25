import { useEffect, useId, useState } from 'react'
import { eur, pct, signedEur } from '../lib/tradeStory'
import { fetchPositionScenarios, type PaperScenarios } from '../lib/paper'

function fmtPctOf(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return pct(v, 2)
}

function holdLabel(h: PaperScenarios['holding']['all']): string {
  if (!h || h.median_hours == null) return '—'
  const hours = h.median_hours
  if (hours >= 48) return `${(hours / 24).toFixed(1)} j (${h.median_bars?.toFixed(0) ?? '—'} bougies)`
  return `${hours.toFixed(1)} h (${h.median_bars?.toFixed(0) ?? '—'} bougies)`
}

/**
 * Tableau Objectif / Stop / Crash + durée / financement / espérance.
 * Données historiques — jamais une prévision.
 */
export function ScenariosPanel({
  scenarios,
  variant = 'preview',
  compact,
}: {
  scenarios: PaperScenarios | null | undefined
  variant?: 'preview' | 'open'
  compact?: boolean
}) {
  if (!scenarios) return null

  const rows =
    variant === 'open' && scenarios.from_mark
      ? [
          {
            key: 'target',
            label: 'Objectif',
            tone: 'target' as const,
            net: scenarios.from_mark.target.net_eur_from_mark,
            pctInv: scenarios.from_mark.target.pct_of_invested,
            pctEq: scenarios.from_mark.target.pct_of_equity,
            note: 'depuis le cours actuel',
          },
          {
            key: 'stop',
            label: 'Stop',
            tone: 'stop' as const,
            net: scenarios.from_mark.stop.net_eur_from_mark,
            pctInv: scenarios.from_mark.stop.pct_of_invested,
            pctEq: scenarios.from_mark.stop.pct_of_equity,
            note: 'depuis le cours actuel',
          },
          {
            key: 'crash',
            label: 'Crash',
            tone: 'crash' as const,
            net: scenarios.from_mark.crash.net_eur_from_mark,
            pctInv: scenarios.from_mark.crash.pct_of_invested,
            pctEq: scenarios.from_mark.crash.pct_of_equity,
            note: 'depuis le cours actuel',
          },
        ]
      : [
          {
            key: 'target',
            label: scenarios.target.label,
            tone: 'target' as const,
            net: scenarios.target.net_eur,
            pctInv: scenarios.target.pct_of_invested,
            pctEq: scenarios.target.pct_of_equity,
            note: undefined as string | undefined,
          },
          {
            key: 'stop',
            label: scenarios.stop.label,
            tone: 'stop' as const,
            net: scenarios.stop.net_eur,
            pctInv: scenarios.stop.pct_of_invested,
            pctEq: scenarios.stop.pct_of_equity,
            note: undefined as string | undefined,
          },
          {
            key: 'crash',
            label: scenarios.crash.label,
            tone: 'crash' as const,
            net: scenarios.crash.net_eur,
            pctInv: scenarios.crash.pct_of_invested,
            pctEq: scenarios.crash.pct_of_equity,
            note: undefined as string | undefined,
          },
        ]

  const exp = scenarios.expectancy
  const holdAll = scenarios.holding.all
  const fin = scenarios.holding.financing_eur_median

  return (
    <section className={`scenarios-panel${compact ? ' is-compact' : ''}`} aria-label="Scénarios">
      <p className="scenarios-disclaimer muted">{scenarios.disclaimer}</p>
      <div className="scenarios-table-wrap">
        <table className="scenarios-table">
          <thead>
            <tr>
              <th scope="col">Scénario</th>
              <th scope="col">€</th>
              <th scope="col">% montant</th>
              <th scope="col">% capital</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key} className={`scenarios-row is-${r.tone}`}>
                <th scope="row">{r.label}</th>
                <td className="mono">{signedEur(r.net)}</td>
                <td className="mono">{fmtPctOf(r.pctInv)}</td>
                <td className="mono">{fmtPctOf(r.pctEq)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <dl className="scenarios-meta">
        <div>
          <dt>Durée typique</dt>
          <dd>
            {holdLabel(holdAll)}
            {scenarios.holding.winners?.median_hours != null && (
              <span className="muted">
                {' '}
                · gagnants {holdLabel(scenarios.holding.winners)} · perdants{' '}
                {holdLabel(scenarios.holding.losers)}
              </span>
            )}
          </dd>
        </div>
        <div>
          <dt>Frais de détention estimés</dt>
          <dd className="mono">
            {fin != null ? eur(fin) : '—'}
            {scenarios.holding.financing_bps_per_day === 0 && (
              <span className="muted"> · spot crypto (0)</span>
            )}
          </dd>
        </div>
        <div>
          <dt>Espérance (net_v2)</dt>
          <dd>
            {exp.available && exp.expectancy_eur != null ? (
              <>
                <span className="mono">{signedEur(exp.expectancy_eur)}</span>
                <span className="muted">
                  {' '}
                  / trade · WR {(exp.win_rate_net != null ? exp.win_rate_net * 100 : 0).toFixed(0)} % · n=
                  {exp.n}
                </span>
              </>
            ) : (
              <span className="muted">{exp.message ?? 'échantillon insuffisant'}</span>
            )}
          </dd>
        </div>
        {scenarios.backtest_window?.n_bars ? (
          <div>
            <dt>Fenêtre historique</dt>
            <dd className="muted">
              {scenarios.backtest_window.n_bars} bougies · {scenarios.backtest_window.metrics_basis}
            </dd>
          </div>
        ) : null}
        {variant === 'open' && scenarios.elapsed && (
          <div>
            <dt>Temps écoulé</dt>
            <dd>
              {scenarios.elapsed.hours.toFixed(1)} h
              {scenarios.elapsed.median_hours != null && (
                <span className="muted">
                  {' '}
                  / médiane {scenarios.elapsed.median_hours.toFixed(1)} h
                </span>
              )}
            </dd>
          </div>
        )}
        {variant === 'open' && scenarios.financing && (
          <div>
            <dt>Financement</dt>
            <dd className="mono">
              payé {eur(scenarios.financing.paid_eur)}
              {scenarios.financing.estimated_remaining_to_median_eur != null && (
                <>
                  {' '}
                  · reste estimé {eur(scenarios.financing.estimated_remaining_to_median_eur)}
                </>
              )}
            </dd>
          </div>
        )}
      </dl>
    </section>
  )
}

/** Dépliant Scénarios pour une position ouverte (Synthèse). */
export function PositionScenariosDisclosure({ positionId }: { positionId: string }) {
  const id = useId()
  const [open, setOpen] = useState(false)
  const [scenarios, setScenarios] = useState<PaperScenarios | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open) return
    let alive = true
    setLoading(true)
    setErr(null)
    fetchPositionScenarios(positionId)
      .then((s) => {
        if (alive) setScenarios(s)
      })
      .catch((e: unknown) => {
        if (alive) setErr(e instanceof Error ? e.message : 'Scénarios indisponibles')
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [open, positionId])

  return (
    <div className="scenarios-disclosure">
      <button
        type="button"
        className="ghost scenarios-disclosure-toggle"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((v) => !v)}
      >
        {open ? 'Masquer scénarios' : 'Scénarios…'}
      </button>
      {open && (
        <div id={id} className="scenarios-disclosure-body">
          {loading && <p className="muted">Calcul…</p>}
          {err && (
            <div className="banner error" role="alert">
              {err}
            </div>
          )}
          {!loading && !err && <ScenariosPanel scenarios={scenarios} variant="open" compact />}
        </div>
      )}
    </div>
  )
}
