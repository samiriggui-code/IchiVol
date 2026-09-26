/**
 * AIAnalysisPanel — texte d'analyse + état du Decision Engine, fournis par
 * Python / agent. Le LLM n'est jamais l'autorité de décision : ce panneau affiche.
 */

import {
  analysisTone,
  fmtPct,
  fmtTime,
  type IntelligenceAnalysis,
  type MarketState,
} from '../../lib/chartIntelligence'

interface Props {
  analysis: IntelligenceAnalysis | null
  marketState?: MarketState | null
  asOf?: number | null
}

const TREND_TONE: Record<MarketState['trend'], string> = {
  bullish: 'green',
  bearish: 'red',
  range: 'gray',
}

export function AIAnalysisPanel({ analysis, marketState, asOf }: Props) {
  return (
    <section className="ci-card ci-analysis" aria-label="AI Analyst">
      <header className="ci-card-head">
        <div>
          <div className="ci-eyebrow">AI ANALYST</div>
          <h3>Lecture du graphique</h3>
        </div>
        <small className="ci-meta">as_of {fmtTime(asOf)}</small>
      </header>

      {marketState && (
        <div className="ci-state-row">
          <span className={`ci-tag ${TREND_TONE[marketState.trend]}`}>{marketState.trend.toUpperCase()}</span>
          <span className="ci-tag gray">{marketState.structure}</span>
          <span className="ci-tag gray">VOL {marketState.volatility.toUpperCase()}</span>
          <span className={`ci-tag ${marketState.rvol >= 1.5 ? 'green' : 'amber'}`}>
            RVOL {marketState.rvol.toFixed(2).replace('.', ',')}×
          </span>
        </div>
      )}

      {!analysis ? (
        <p className="ci-muted">Pas encore d’analyse à cet instant du replay.</p>
      ) : (
        <>
          <p className="ci-summary">{analysis.summary}</p>
          {analysis.confluence && analysis.confluence.length > 0 && (
            <div className="ci-block">
              <div className="ci-eyebrow">CONFLUENCE</div>
              <ul className="ci-list">
                {analysis.confluence.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
            </div>
          )}
          <div className="ci-decision">
            <div className="ci-eyebrow">DECISION ENGINE</div>
            <div className="ci-decision-state">
              <span className={`ci-tag ci-tag-lg ${analysisTone(analysis.state)}`}>{analysis.state}</span>
              <small className="ci-meta">conf. {fmtPct(analysis.confidence)}</small>
            </div>
            {analysis.waiting && analysis.waiting.length > 0 && (
              <div className="ci-waiting">
                <span>Waiting:</span>
                {analysis.waiting.map((w) => (
                  <b key={w} className="mono">
                    {w}
                  </b>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </section>
  )
}
