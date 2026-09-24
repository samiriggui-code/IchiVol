import { Link } from 'react-router-dom'
import { DecisionPipelinePanel } from './DecisionPipelinePanel'
import { VerdictBadge } from './VerdictBadge'
import type { DecisionDetail } from '../lib/decisions'
import type { DecisionPipelineView } from '../lib/decisionPipeline'
import { pipelineHeadline, stageStatusLabel } from '../lib/decisionPipeline'
import { signalLabel } from '../lib/signals'
import type { Signal } from '../lib/types'

interface Props {
  symbol: string
  signals: Signal[]
  bias: 'bull' | 'bear' | 'neutral'
  rvol: number
  price: number | null
  /** Décision moteur Python (crypto USDT) — null si hors périmètre / erreur. */
  engineDetail: DecisionDetail | null
  enginePipeline: DecisionPipelineView | null
  engineLoading: boolean
  engineError: string | null
  engineAvailable: boolean
  /** Maquette CTA — ouvre le marquage / préparation trade. */
  onPrepareTrade?: () => void
  prepareTradeDisabled?: boolean
}

export function BiasPanel({
  symbol,
  signals,
  bias,
  rvol,
  price,
  engineDetail,
  enginePipeline,
  engineLoading,
  engineError,
  engineAvailable,
  onPrepareTrade,
  prepareTradeDisabled,
}: Props) {
  const recent = [...signals].reverse().slice(0, 6)
  const gateRows = enginePipeline?.stages ?? []
  return (
    <section className="panel bias-panel analysis-panel">
      <header className="panel-head">
        <h2>Lecture du marché</h2>
        <span className="panel-meta">{symbol}</span>
      </header>

      <div className="bias-body card-body">
        {gateRows.length > 0 ? (
          <div className="mkt-gate-stats" aria-label="Portes du pipeline">
            {gateRows.map((stage) => (
              <div key={stage.id} className="statline">
                <span>{stage.label}</span>
                <span className={`mkt-gate-badge mkt-gate-badge--${stage.status}`}>
                  {stageStatusLabel(stage.status).toUpperCase()}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="bias-grid">
            <div>
              <span className="label">Biais chart</span>
              <strong className={`bias bias-${bias}`}>{bias}</strong>
            </div>
            <div>
              <span className="label">RVOL chart</span>
              <strong className="mono">{rvol.toFixed(2)}×</strong>
            </div>
            <div>
              <span className="label">Prix</span>
              <strong className="mono">
                {price != null
                  ? price.toLocaleString(undefined, { maximumFractionDigits: 6 })
                  : '—'}
              </strong>
            </div>
          </div>
        )}

        {enginePipeline && (
          <p className="mkt-analysis-blurb muted">{pipelineHeadline(enginePipeline)}</p>
        )}

        <div className="bias-engine">
          <div className="bias-engine-head">
            <h3 className="subhead">Moteur IchiVol</h3>
            {engineAvailable && engineDetail && (
              <Link
                to="/app/opportunites"
                className="ghost bias-engine-link"
                title="Ouvrir la page Décisions"
              >
                Décisions →
              </Link>
            )}
          </div>

          {!engineAvailable && (
            <p className="muted bias-engine-msg">
              Le moteur décisionnel (pipeline) est branché sur les paires crypto USDT. Change de
              classe / timeframe supporté pour l’activer.
            </p>
          )}

          {engineAvailable && engineLoading && !engineDetail && (
            <p className="muted bias-engine-msg">Chargement moteur…</p>
          )}

          {engineAvailable && engineError && (
            <p className="bias-engine-msg error-text" role="alert">
              {engineError.includes('engine_unreachable') || engineError.includes('502')
                ? 'Moteur Python injoignable (port 8000).'
                : engineError}
            </p>
          )}

          {engineDetail && (
            <>
              <div className="bias-engine-badges">
                <VerdictBadge decision={engineDetail.decision} pipeline={engineDetail.pipeline} />
                <span className="muted mono">
                  conf {(engineDetail.confidence * 100).toFixed(0)}% · {engineDetail.timeframe}
                  {enginePipeline?.native ? ' · natif' : ''}
                </span>
              </div>
              <div className="step mkt-setup-step">
                <b>{setupStepTitle(engineDetail.direction, enginePipeline)}</b>
                <p>
                  RVOL attendu ≥ 1,5
                  {liveRvolHint(rvol)}
                </p>
                <span className="mkt-gate-badge mkt-gate-badge--pass">ARMED</span>
              </div>
              {enginePipeline && <DecisionPipelinePanel view={enginePipeline} />}
            </>
          )}
        </div>

        <div className="mkt-analysis-ctas">
          {onPrepareTrade ? (
            <button
              type="button"
              className="mkt-cta-primary"
              disabled={prepareTradeDisabled}
              onClick={onPrepareTrade}
            >
              Préparer le trade →
            </button>
          ) : null}
          <Link to="/app/watchlist" className="mkt-cta-secondary">
            Ajouter à la watchlist
          </Link>
        </div>

        <h3 className="subhead">Signaux chart (RVOL local)</h3>
        <ul className="signal-list">
          {recent.map((s) => (
            <li key={`${s.time}-${s.kind}`}>
              <span className="sig-chip">{signalLabel(s.kind)}</span>
              <span className="mono muted">{new Date(s.time * 1000).toLocaleString()}</span>
              <span className="mono">{s.rvol.toFixed(2)}×</span>
            </li>
          ))}
          {recent.length === 0 && (
            <li className="muted">Pas de signal volume-confirmé sur la fenêtre chart</li>
          )}
        </ul>
      </div>
    </section>
  )
}

function liveRvolHint(rvol: number): string {
  if (!Number.isFinite(rvol) || rvol <= 0) return ''
  return ` · chart ${rvol.toFixed(2)}×`
}

function setupStepTitle(
  direction: DecisionDetail['direction'],
  pipeline: DecisionPipelineView | null,
): string {
  const structure = pipeline?.stages.find((s) => s.id === 'structure')
  if (structure?.summary && structure.status !== 'pending') {
    return structure.summary.length > 48
      ? `${structure.summary.slice(0, 45)}…`
      : structure.summary
  }
  if (direction === 'LONG') return 'Pullback haussier'
  if (direction === 'SHORT') return 'Pullback baissier'
  return 'Attente de setup'
}
