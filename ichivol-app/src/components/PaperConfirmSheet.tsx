import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { labelPipelineGate } from '../lib/decisionLabels'
import type { PipelineGateLabel } from '../lib/decisions'
import type { OrderIntent } from '../lib/paper'

function fmt(v: number | null | undefined, digits = 4): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return v.toPrecision(digits)
}

function fmtEur(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 2,
  }).format(v)
}

/**
 * Backdrop de confirmation paper — avant toute ouverture virtuelle.
 * Aucun ordre live.
 */
export function PaperConfirmSheet({
  symbolLabel,
  intent,
  confirming,
  onConfirm,
  onCancel,
}: {
  symbolLabel: string
  intent: OrderIntent
  confirming?: boolean
  onConfirm: () => void
  onCancel: () => void
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !confirming) onCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onCancel, confirming])

  return (
    <div
      className="trade-sheet-backdrop paper-confirm-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="Confirmer l’ordre paper"
      onClick={(e) => {
        if (e.target === e.currentTarget && !confirming) onCancel()
      }}
    >
      <aside className="panel trade-sheet paper-confirm-sheet">
        <header className="panel-head trade-sheet-head">
          <div>
            <h2>Confirmer l’ordre paper</h2>
            <p className="muted">
              {symbolLabel} · virtuel — aucun broker réel
            </p>
          </div>
          <button type="button" className="ghost" onClick={onCancel} disabled={confirming}>
            Fermer
          </button>
        </header>

        <div className="trade-sheet-scroll">
          {!intent.actionable && (
            <div className="banner error" role="alert">
              Ordre non actionnable — Portes ≠ Achat/Vente ou risque insuffisant (
              {intent.reason}).
            </div>
          )}

          <div className="trade-sheet-brief">
            <p className="subhead">Récapitulatif</p>
            <p>
              Portes :{' '}
              <strong>
                {labelPipelineGate(intent.pipeline_decision as PipelineGateLabel) ||
                  intent.pipeline_decision}
              </strong>
              {' · '}
              Sens : <strong>{intent.direction ?? '—'}</strong>
            </p>
            <p>
              Prix entrée estimé <span className="mono">{fmt(intent.price)}</span>
              {intent.entry_fill != null && (
                <>
                  {' '}
                  (fill <span className="mono">{fmt(intent.entry_fill)}</span>)
                </>
              )}
            </p>
          </div>

          <dl className="propose-stats paper-confirm-stats">
            <div>
              <dt>Quantité</dt>
              <dd className="mono">{fmt(intent.qty, 5)}</dd>
            </div>
            <div>
              <dt>Notional</dt>
              <dd className="mono">{fmtEur(intent.notional)}</dd>
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
                {intent.risk_pct != null ? `${(intent.risk_pct * 100).toFixed(1)} %` : '—'}
                {intent.risk_amount != null ? ` · ${fmtEur(intent.risk_amount)}` : ''}
              </dd>
            </div>
            <div>
              <dt>Cash libre</dt>
              <dd className="mono">{fmtEur(intent.cash)}</dd>
            </div>
          </dl>

          <p className="muted paper-confirm-note">
            Confirmer ouvre une position paper et un snapshot journal. Ensuite :{' '}
            <Link to="/app/synthese">Synthèse</Link> (compte) ·{' '}
            <Link to="/app/paper">Paper</Link> (positions) ·{' '}
            <Link to="/app/journal">Journal</Link> (snapshots).
          </p>

          <div className="paper-confirm-actions">
            <button
              type="button"
              className="ghost"
              disabled={!intent.actionable || confirming}
              onClick={onConfirm}
            >
              {confirming ? 'Ouverture…' : 'Confirmer (paper)'}
            </button>
            <button type="button" className="ghost" disabled={confirming} onClick={onCancel}>
              Annuler
            </button>
          </div>
        </div>
      </aside>
    </div>
  )
}
