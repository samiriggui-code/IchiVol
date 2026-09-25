import { Link } from 'react-router-dom'
import { DecisionPipelinePanel } from './DecisionPipelinePanel'
import { VerdictBadge } from './VerdictBadge'
import type { DecisionDetail } from '../lib/decisions'
import type { DecisionPipelineView } from '../lib/decisionPipeline'
import { signalLabel } from '../lib/signals'
import type { Signal } from '../lib/types'
import './BiasPanel.css'

interface Props {
  symbol: string
  signals: Signal[]
  bias: 'bull' | 'bear' | 'neutral'
  rvol: number | null
  price: number | null
  /** Décision moteur Python (crypto USDT) — null si hors périmètre / erreur. */
  engineDetail: DecisionDetail | null
  enginePipeline: DecisionPipelineView | null
  engineLoading: boolean
  engineError: string | null
  engineAvailable: boolean
  /** Ouvre le flux « Préparer le trade » (MarkTradeSheet modal). */
  onPrepareTrade?: () => void
  prepareTradeDisabled?: boolean
  prepareTradeHint?: string | null
}

function fmtRvol(n: number | null): string {
  if (n == null || !Number.isFinite(n)) return '—'
  return `${n.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}×`
}

function fmtPrice(n: number | null): string {
  if (n == null || !Number.isFinite(n)) return '—'
  return n.toLocaleString('fr-FR', {
    maximumFractionDigits: n >= 100 ? 2 : 6,
  })
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
  prepareTradeHint,
}: Props) {
  const recent = [...signals].reverse().slice(0, 6)
  const showPrepare = typeof onPrepareTrade === 'function'

  return (
    <section className="panel bias-panel bias-panel--lecture">
      <header className="panel-head">
        <h2>Lecture du marché</h2>
        <span className="panel-meta">{symbol}</span>
      </header>

      <div className="bias-meta-strip" aria-label="Résumé chart">
        <span>
          Biais chart <strong className={`bias bias-${bias}`}>{bias}</strong>
        </span>
        <span>
          RVOL <strong className="mono">{fmtRvol(rvol)}</strong>
        </span>
        <span>
          Prix <strong className="mono">{fmtPrice(price)}</strong>
        </span>
      </div>
      <p className="bias-chart-note">
        Chart = OHLCV source (calcul local). Les 5 portes ci-dessous viennent du moteur IchiVol
        (même lecture que Décisions).
      </p>

      <div className="bias-engine">
        <div className="bias-engine-head">
          <h3 className="subhead">Cinq portes</h3>
          {engineAvailable && engineDetail && (
            <Link
              to="/app/opportunites"
              className="bias-engine-link"
              title="Ouvrir la page Décisions"
            >
              Décisions →
            </Link>
          )}
        </div>

        {!engineAvailable && (
          <p className="muted bias-engine-msg">
            Pipeline décisionnel branché sur les paires crypto USDT. Change de classe / timeframe
            supporté pour l’activer.
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

        {engineAvailable && !engineLoading && !engineError && !engineDetail && (
          <p className="muted bias-engine-msg">Non disponible</p>
        )}

        {engineDetail && (
          <>
            <div className="bias-engine-badges">
              <VerdictBadge decision={engineDetail.decision} pipeline={engineDetail.pipeline} />
              <span className="muted mono">
                conf{' '}
                {(engineDetail.confidence * 100).toLocaleString('fr-FR', {
                  maximumFractionDigits: 0,
                })}
                % · {engineDetail.timeframe}
                {enginePipeline?.native ? ' · natif' : ''}
              </span>
            </div>
            {enginePipeline && <DecisionPipelinePanel view={enginePipeline} />}
          </>
        )}
      </div>

      <div className="bias-signals">
        <h3 className="subhead">Signaux chart (RVOL local)</h3>
        <ul className="signal-list">
          {recent.map((s) => (
            <li key={`${s.time}-${s.kind}`}>
              <span className="sig-chip">{signalLabel(s.kind)}</span>
              <span className="mono muted">
                {new Date(s.time * 1000).toLocaleString('fr-FR')}
              </span>
              <span className="mono">{fmtRvol(s.rvol)}</span>
            </li>
          ))}
          {recent.length === 0 && (
            <li className="muted">Pas de signal volume-confirmé sur la fenêtre chart</li>
          )}
        </ul>
      </div>

      {showPrepare && (
        <div className="bias-cta-row">
          <button
            type="button"
            className="bias-prepare-cta"
            disabled={prepareTradeDisabled}
            title={
              prepareTradeDisabled
                ? (prepareTradeHint ?? 'Marquage indisponible sur ce symbole / TF')
                : 'Poser ENTRY / STOP / TARGET puis proposer en paper'
            }
            onClick={onPrepareTrade}
          >
            Préparer le trade →
          </button>
          {prepareTradeDisabled && prepareTradeHint ? (
            <p className="bias-cta-hint">{prepareTradeHint}</p>
          ) : null}
        </div>
      )}
    </section>
  )
}
