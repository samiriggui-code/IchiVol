import { labelPipelineGate } from '../lib/decisionLabels'
import type { PipelineGateLabel } from '../lib/decisions'
import type { OrderIntent } from '../lib/paper'

function fmt(v: number | null | undefined, digits = 4): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return v.toPrecision(digits)
}

function reasonLabel(reason: string): string {
  switch (reason) {
    case 'ok':
      return 'Prêt à ouvrir (paper)'
    case 'not_actionable':
      return 'Pas d’entrée — Portes = Surveillance / Pas de trade'
    case 'no_stop':
      return 'Stop ATR indisponible'
    case 'insufficient_cash_or_risk':
      return 'Cash / risque insuffisant'
    default:
      return reason
  }
}

/**
 * FRONT — ProposePaperTradePanel
 * Affiche l’intent paper (qty / stop / TP) avant confirmation.
 * N’envoie jamais d’ordre live.
 */
export function ProposePaperTradePanel({
  intent,
  loading,
  confirming,
  onConfirm,
  onRefresh,
}: {
  intent: OrderIntent | null
  loading?: boolean
  confirming?: boolean
  onConfirm: () => void
  onRefresh?: () => void
}) {
  if (loading && !intent) {
    return <p className="muted propose-paper-loading">Calcul de l’ordre paper…</p>
  }
  if (!intent) return null

  return (
    <section className="propose-paper-panel" aria-label="Ordre paper proposé">
      <header className="propose-paper-head">
        <span className="subhead">Ordre paper proposé</span>
        <span className={`propose-badge ${intent.actionable ? 'is-ok' : 'is-block'}`}>
          {intent.actionable ? 'Prêt' : 'Bloqué'}
        </span>
      </header>

      <p className="propose-reason">{reasonLabel(intent.reason)}</p>

      <dl className="propose-stats">
        <div>
          <dt>Portes</dt>
          <dd>
            {labelPipelineGate(intent.pipeline_decision as PipelineGateLabel) ||
              intent.pipeline_decision}
          </dd>
        </div>
        <div>
          <dt>Direction</dt>
          <dd>{intent.direction ?? '—'}</dd>
        </div>
        <div>
          <dt>Prix</dt>
          <dd className="mono">{fmt(intent.price)}</dd>
        </div>
        <div>
          <dt>Qty</dt>
          <dd className="mono">{fmt(intent.qty, 5)}</dd>
        </div>
        <div>
          <dt>Notional</dt>
          <dd className="mono">{fmt(intent.notional, 5)}</dd>
        </div>
        <div>
          <dt>Stop</dt>
          <dd className="mono">{fmt(intent.stop_price)}</dd>
        </div>
        <div>
          <dt>Take profit</dt>
          <dd className="mono">{fmt(intent.take_profit_price)}</dd>
        </div>
        <div>
          <dt>Risque</dt>
          <dd className="mono">
            {intent.risk_pct != null ? `${(intent.risk_pct * 100).toFixed(1)}%` : '—'}
          </dd>
        </div>
      </dl>

      {intent.evidence_summary && (
        <p className="muted propose-evidence-note">
          Evidence · n={intent.evidence_summary.sample_size} ·{' '}
          {intent.evidence_summary.status}
        </p>
      )}

      <div className="propose-actions">
        <button
          type="button"
          className="ghost"
          disabled={!intent.actionable || confirming}
          onClick={onConfirm}
        >
          {confirming ? '…' : 'Vérifier et confirmer…'}
        </button>
        {onRefresh && (
          <button type="button" className="ghost" disabled={loading} onClick={onRefresh}>
            Recalculer
          </button>
        )}
        <span className="muted">Virtuel — aucun broker réel.</span>
      </div>
    </section>
  )
}
