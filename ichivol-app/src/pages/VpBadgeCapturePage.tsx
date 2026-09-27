/**
 * Page hors-auth pour captures docs/ui-vp-badge (B1).
 * ?view=matrix|decision|position — thème via html.dark.
 */
import { VerdictBadge } from '../components/VerdictBadge'
import { VpValidationBadge } from '../components/VpValidationBadge'
import type { DecisionLabel, DecisionPipelinePayload } from '../lib/decisions'

const buyPipeline: DecisionPipelinePayload = {
  decision: 'BUY',
  direction: 'LONG',
  strategy_version: 'north-star-v1',
  stages: [
    { id: 'direction', status: 'pass', summary: 'LONG' },
    { id: 'participation', status: 'pass', summary: 'RVOL 1.9' },
    { id: 'structure', status: 'pass', summary: 'HH/HL' },
    { id: 'location', status: 'pass', summary: 'Pullback' },
    { id: 'regime', status: 'pass', summary: 'Tendance' },
  ],
}

function badge(text: string, tone: 'bull' | 'bear' | 'gray' = 'bull') {
  return <span className={`bias bias-${tone === 'gray' ? 'neutral' : tone}`}>{text}</span>
}

function MatrixView() {
  return (
    <div className="dash-main" data-capture="matrix">
      <header className="page-head">
        <p className="eyebrow">03 / ICHIVOL WORKSPACE</p>
        <h1>Opportunités</h1>
        <p>Chaque décision commence par une preuve.</p>
      </header>
      <section className="card">
        <div className="card-head">
          <h2>Matrice de décision</h2>
          <span className="pill">5 PORTES</span>
        </div>
        <div className="card-body" style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>ACTIF</th>
                <th>DIRECTION</th>
                <th>VERDICT</th>
                <th>RVOL</th>
                <th>CONFIANCE</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>BTC</td>
                <td>
                  <span className="up">↑ Achat</span>
                </td>
                <td>
                  <VerdictBadge decision={'BUY' as DecisionLabel} pipeline={buyPipeline} />
                </td>
                <td>1.90</td>
                <td>72</td>
              </tr>
              <tr>
                <td>ETH</td>
                <td>
                  <span className="down">↓ Vente</span>
                </td>
                <td>
                  <VerdictBadge
                    decision={'SELL' as DecisionLabel}
                    pipeline={{ ...buyPipeline, decision: 'SELL', direction: 'SHORT' }}
                  />
                </td>
                <td>2.10</td>
                <td>68</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

function DecisionView() {
  return (
    <div className="dash-main" data-capture="decision">
      <div className="dialog-body" style={{ maxWidth: 520, margin: '24px auto', padding: 20 }}>
        <div className="dialog-head">
          <h2>BTC / USDT</h2>
          <button type="button" aria-label="Fermer">
            ×
          </button>
        </div>
        {badge('DÉCLENCHÉ')}
        <p>Fiche de décision · Ichimoku × RVOL · 1H · north-star-v1</p>
        <div className="statline">
          <span>Direction</span>
          <b>
            {badge('PASSE')} <VpValidationBadge />
          </b>
        </div>
        <div className="statline">
          <span>Participation</span>
          <b>{badge('PASSE')}</b>
        </div>
        <div className="statline">
          <span>RVOL</span>
          <b>1.90</b>
        </div>
        <div className="statline">
          <span>Confiance</span>
          <b>72 %</b>
        </div>
        <div className="engine-evidence" style={{ marginTop: 16 }}>
          <div className="decision-pipeline-head">
            <span className="subhead">Pipeline</span>
            <span className="pipeline-headline muted">BUY · portes alignées</span>
          </div>
          <div className="pipeline-gate-row">
            <span className="muted">Verdict portes</span>
            <span className="bias bias-bull">ACHAT</span>
          </div>
        </div>
      </div>
    </div>
  )
}

function PositionView() {
  return (
    <div className="dash-main" data-capture="position">
      <div className="pf-fiche" style={{ maxWidth: 420, margin: '16px auto' }}>
        <div className="pf-fiche-body">
          <div className="dialog-head">
            <h2>BTC · LONG · 1H</h2>
            <button type="button" aria-label="Fermer">
              ×
            </button>
          </div>
          <p>
            Ouverte après votre confirmation. Entrée le{' '}
            {new Date(Date.now() - 86400000).toLocaleString('fr-FR')} à 96 000. Signal : BUY.{' '}
            <VpValidationBadge />
          </p>
          <div className="statline">
            <span>Quantité</span>
            <b>0,01</b>
          </div>
          <div className="statline">
            <span>Notionnel</span>
            <b>960 €</b>
          </div>
          <div className="statline">
            <span>Stop</span>
            <b>94 000</b>
          </div>
        </div>
      </div>
    </div>
  )
}

export function VpBadgeCapturePage() {
  const params = new URLSearchParams(typeof window !== 'undefined' ? window.location.search : '')
  const view = params.get('view') || 'matrix'
  return (
    <div className="dash-shell" data-page="vp-badge-capture">
      <div className="dash-topbar" style={{ padding: '8px 16px', display: 'flex', gap: 12, alignItems: 'center' }}>
        <strong>IchiVol</strong>
        <span className="dash-paper-pill">PAPER</span>
      </div>
      {view === 'decision' ? <DecisionView /> : null}
      {view === 'position' ? <PositionView /> : null}
      {view === 'matrix' || (!['decision', 'position'].includes(view)) ? <MatrixView /> : null}
    </div>
  )
}
