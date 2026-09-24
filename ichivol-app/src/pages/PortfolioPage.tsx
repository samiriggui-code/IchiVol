import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { PaperPage } from './PaperPage'
import { SynthesePage } from './SynthesePage'
import './PortfolioPage.css'

type PortfolioTab = 'synthese' | 'compte' | 'positions' | 'tests'

function normalizeTab(raw: string | null): PortfolioTab {
  if (raw === 'positions' || raw === 'paper') return 'positions'
  if (raw === 'compte' || raw === 'account') return 'compte'
  if (raw === 'tests') return 'tests'
  return 'synthese'
}

/**
 * T14a — Portefeuille = Synthèse + Paper en onglets (Compte · Positions · Tests).
 * Réutilise les pages existantes ; pas de nouveau moteur.
 */
export function PortfolioPage() {
  const [params, setParams] = useSearchParams()
  const active = useMemo(() => normalizeTab(params.get('tab')), [params])

  function selectTab(next: PortfolioTab) {
    const nextParams = new URLSearchParams(params)
    if (next === 'synthese') nextParams.delete('tab')
    else nextParams.set('tab', next === 'positions' ? 'positions' : next)
    setParams(nextParams, { replace: true })
  }

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
