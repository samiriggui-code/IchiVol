import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { getPaperOverview, type PaperOverview } from '../lib/paper'
import { PaperPage } from './PaperPage'
import { SynthesePage } from './SynthesePage'
import './PortfolioPage.css'

type PortfolioTab = 'synthese' | 'compte' | 'positions' | 'risque' | 'tests'

function normalizeTab(raw: string | null): PortfolioTab {
  if (raw === 'positions' || raw === 'paper') return 'positions'
  if (raw === 'compte' || raw === 'account') return 'compte'
  if (raw === 'risque' || raw === 'risk') return 'risque'
  if (raw === 'tests') return 'tests'
  return 'synthese'
}

function fmtPct(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return `${(v * 100).toFixed(2)} %`
}

function fmtMoney(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return v.toLocaleString('fr-FR', { maximumFractionDigits: 2 })
}

/**
 * T14a + T13b — Portefeuille = Synthèse + Paper + onglet Risque.
 */
export function PortfolioPage() {
  const [params, setParams] = useSearchParams()
  const active = useMemo(() => normalizeTab(params.get('tab')), [params])
  const [overview, setOverview] = useState<PaperOverview | null>(null)
  const [riskError, setRiskError] = useState<string | null>(null)

  useEffect(() => {
    if (active !== 'risque') return
    let cancelled = false
    getPaperOverview()
      .then((ov) => {
        if (!cancelled) {
          setOverview(ov)
          setRiskError(null)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setRiskError(err instanceof Error ? err.message : 'Risque indisponible')
        }
      })
    return () => {
      cancelled = true
    }
  }, [active])

  function selectTab(next: PortfolioTab) {
    const nextParams = new URLSearchParams(params)
    if (next === 'synthese') nextParams.delete('tab')
    else nextParams.set('tab', next === 'positions' ? 'positions' : next)
    setParams(nextParams, { replace: true })
  }

  const risk = overview?.risk

  return (
    <div className="portfolio-page">
      <header className="page-header portfolio-page-header">
        <div>
          <p className="eyebrow muted">Trading</p>
          <h1>Portefeuille</h1>
          <p className="muted portfolio-page-sub">Le capital d’abord. Le risque toujours.</p>
        </div>
      </header>

      <div className="portfolio-tabs" role="tablist" aria-label="Sections portefeuille">
        {(
          [
            ['synthese', 'Synthèse'],
            ['compte', 'Compte'],
            ['positions', 'Positions'],
            ['risque', 'Risque'],
            ['tests', 'Tests'],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={active === id}
            className={`portfolio-tab${active === id ? ' is-active' : ''}`}
            onClick={() => selectTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="portfolio-tab-panel" role="tabpanel">
        {active === 'synthese' && (
          <div className="portfolio-embed is-synthese">
            <SynthesePage />
          </div>
        )}
        {active === 'compte' && (
          <div className="portfolio-embed">
            <p className="muted portfolio-embed-hint">
              Vue compte paper — détail technique aussi dans{' '}
              <Link to="/app/portefeuille?tab=positions">Positions</Link>.
            </p>
            <PaperPage />
          </div>
        )}
        {active === 'positions' && (
          <div className="portfolio-embed">
            <PaperPage />
          </div>
        )}
        {active === 'risque' && (
          <div className="portfolio-embed portfolio-risk">
            <p className="muted portfolio-embed-hint">
              Risk Kernel (T13b) — capital, exposé, risque utilisé, derniers refus. Kill switch avec
              T13c.
            </p>
            {riskError && (
              <div className="banner error" role="alert">
                {riskError}
              </div>
            )}
            {!riskError && !risk && <p className="muted">Chargement…</p>}
            {risk && (
              <>
                <dl className="portfolio-risk-grid">
                  <div>
                    <dt>Capital (equity)</dt>
                    <dd className="mono">{fmtMoney(risk.capital)}</dd>
                  </div>
                  <div>
                    <dt>Cash</dt>
                    <dd className="mono">{fmtMoney(risk.cash)}</dd>
                  </div>
                  <div>
                    <dt>Exposé</dt>
                    <dd className="mono">{fmtMoney(risk.exposed)}</dd>
                  </div>
                  <div>
                    <dt>Risque utilisé</dt>
                    <dd className="mono">
                      {fmtMoney(risk.open_risk_amount)}
                      {risk.open_risk_pct != null ? ` · ${fmtPct(risk.open_risk_pct)}` : ''}
                      {risk.max_open_risk_pct != null
                        ? ` / lim. ${fmtPct(risk.max_open_risk_pct)}`
                        : ''}
                    </dd>
                  </div>
                  <div>
                    <dt>Positions ouvertes</dt>
                    <dd className="mono">
                      {risk.open_positions} / {risk.max_open_positions}
                    </dd>
                  </div>
                </dl>
                <h2 className="portfolio-risk-h2">Derniers refus</h2>
                {risk.recent_refusals.length === 0 ? (
                  <p className="muted">Aucun refus journalisé récemment.</p>
                ) : (
                  <div className="table-wrap">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Quand</th>
                          <th>Symbole</th>
                          <th>TF</th>
                          <th>Code</th>
                        </tr>
                      </thead>
                      <tbody>
                        {risk.recent_refusals.map((r, i) => (
                          <tr key={`${r.at}-${r.symbol}-${i}`}>
                            <td className="mono muted">
                              {r.at ? new Date(r.at).toLocaleString('fr-FR') : '—'}
                            </td>
                            <td>{r.symbol ?? '—'}</td>
                            <td>{r.timeframe ?? '—'}</td>
                            <td className="mono">{(r.codes && r.codes[0]) || r.reason || '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}
          </div>
        )}
        {active === 'tests' && (
          <div className="portfolio-embed">
            <p className="muted portfolio-embed-hint">
              Tests / shadow broker — section Paper. Disponible avec T13x pour un onglet dédié.
            </p>
            <PaperPage />
          </div>
        )}
      </div>
    </div>
  )
}
