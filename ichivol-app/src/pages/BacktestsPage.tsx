import {
  CLASS_BLURBS,
  CLASS_LABELS,
} from '../lib/universe'
import { HistorySheet } from './lab/HistorySheet'
import { LabKpis } from './lab/LabKpis'
import { LabMainContent } from './lab/LabMainContent'
import { LAB_TABS } from './lab/labShared'
import { useLabController } from './lab/useLabController'
import './BacktestsPage.css'

export function BacktestsPage() {
  const c = useLabController()
  const {
    current, visibleClasses, marketClass, selectClass, historyOpen, setHistoryOpen, labTab, setLabTab,
  } = c

  return (
    <div className="backtests-page">
      <header className="iv-page-header page-head market-head">
        <div className="market-head-copy">
          <p className="iv-page-eyebrow">Recherche · Strategy Lab</p>
          <h1>Strategy Lab</h1>
          <p className="iv-page-question">Est-ce que cette méthode tient historiquement ?</p>
          <p className="muted">
            Chiffres depuis la Performance DB (expériences persistées). Onglet{' '}
            <strong>Ablations / WF</strong> = recalcul ponctuel ; <strong>Research</strong> = T5–T7 /
            Researcher (observation only). Pas un conseil financier.
          </p>
          {current && (
            <p className="muted">{CLASS_BLURBS[current.asset_class]}</p>
          )}
        </div>
        <div className="bt-head-actions">
          {visibleClasses.length > 0 && (
            <div className="market-class-tabs" role="tablist" aria-label="Classe d’actif">
              {visibleClasses.map((cl) => (
                <button
                  key={cl}
                  type="button"
                  role="tab"
                  aria-selected={cl === marketClass}
                  className={cl === marketClass ? 'is-active' : undefined}
                  onClick={() => selectClass(cl)}
                >
                  {CLASS_LABELS[cl]}
                </button>
              ))}
            </div>
          )}
          <button
            type="button"
            className={`ghost${historyOpen ? ' is-active' : ''}`}
            aria-pressed={historyOpen}
            onClick={() => setHistoryOpen((o) => !o)}
          >
            Historique
          </button>
        </div>
      </header>

      <div className="market-class-tabs" role="tablist" aria-label="Strategy Lab" style={{ marginBottom: '0.75rem' }}>
        {LAB_TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={labTab === tab.id}
            className={labTab === tab.id ? 'is-active' : undefined}
            onClick={() => setLabTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <LabKpis c={c} />

      <div className={`bt-split${historyOpen ? ' is-open' : ''}`}>
        <div className="bt-main">
          <LabMainContent c={c} />
        </div>
        <HistorySheet c={c} />
      </div>
    </div>
  )
}
