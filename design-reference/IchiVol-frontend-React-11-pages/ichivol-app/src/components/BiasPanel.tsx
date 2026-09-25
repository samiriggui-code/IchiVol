import { Link } from 'react-router-dom'
import { DecisionPipelinePanel } from './DecisionPipelinePanel'
import { VerdictBadge } from './VerdictBadge'
import type { DecisionDetail } from '../lib/decisions'
import type { DecisionPipelineView } from '../lib/decisionPipeline'
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
}: Props) {
  const recent = [...signals].reverse().slice(0, 6)
  return (
    <section className="panel bias-panel">
      <header className="panel-head">
        <h2>Lecture</h2>
        <span className="panel-meta">{symbol}</span>
      </header>

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
      <p className="bias-chart-note muted">
        Chart = OHLCV source (calcul local). Le moteur IchiVol ci-dessous est la même lecture que
        Décisions.
      </p>

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
            {enginePipeline && <DecisionPipelinePanel view={enginePipeline} />}
          </>
        )}
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
    </section>
  )
}
