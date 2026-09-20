import { useEffect, useRef } from 'react'
import type { PaperOverviewPosition, PaperPosition } from '../lib/paper'
import { assetName, directionWords, eur, pct, price, signedEur } from '../lib/tradeStory'

type Closable = PaperPosition | PaperOverviewPosition

function isOverview(p: Closable): p is PaperOverviewPosition {
  return 'current_price' in p || 'unrealized_pnl' in p
}

/**
 * Dialogue de confirmation avant clôture d’une position paper.
 * Garde-fou anti double-clic. Aucun ordre live.
 */
export function PaperCloseConfirmSheet({
  position,
  confirming,
  error,
  onConfirm,
  onCancel,
}: {
  position: Closable
  confirming?: boolean
  error?: string | null
  onConfirm: () => void
  onCancel: () => void
}) {
  const clickLock = useRef(false)

  useEffect(() => {
    if (!confirming) clickLock.current = false
  }, [confirming])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !confirming) onCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onCancel, confirming])

  const dir = directionWords(position.direction)
  const label = assetName(position.symbol)
  const current = isOverview(position) ? position.current_price : null
  const latent = isOverview(position) ? position.unrealized_pnl : null
  const latentPct = isOverview(position) ? position.unrealized_pct : null
  const sourceLabel =
    position.source === 'auto_watchlist'
      ? 'Auto'
      : position.source === 'user_confirmed'
        ? 'Manuel'
        : position.source

  function handleConfirm() {
    if (confirming || clickLock.current) return
    clickLock.current = true
    onConfirm()
  }

  return (
    <div
      className="trade-sheet-backdrop paper-confirm-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="Confirmer la clôture de la position"
      onClick={(e) => {
        if (e.target === e.currentTarget && !confirming) onCancel()
      }}
    >
      <aside className="panel trade-sheet paper-confirm-sheet">
        <header className="panel-head trade-sheet-head">
          <div>
            <h2>Clôturer la position</h2>
            <p className="muted">
              {label} · {dir.title} · virtuel — aucun broker réel
            </p>
          </div>
          <button type="button" className="ghost" onClick={onCancel} disabled={confirming}>
            Annuler
          </button>
        </header>

        <div className="trade-sheet-scroll">
          {error && (
            <div className="banner error" role="alert">
              {error}
            </div>
          )}

          <div className="trade-sheet-brief">
            <p className="subhead">Tu es sur le point de clôturer cette position paper</p>
            <p>
              {label} <span className="muted">({position.symbol})</span> · {position.timeframe} ·{' '}
              {sourceLabel}
            </p>
          </div>

          <dl className="propose-stats paper-confirm-stats">
            <div>
              <dt>Coût d’acquisition</dt>
              <dd className="mono">{eur(position.notional)}</dd>
            </div>
            <div>
              <dt>Quantité</dt>
              <dd className="mono">
                {position.qty != null ? position.qty.toPrecision(4) : '—'}
              </dd>
            </div>
            <div>
              <dt>Entrée</dt>
              <dd className="mono">{price(position.entry_price)}</dd>
            </div>
            <div>
              <dt>Cours (indicatif)</dt>
              <dd className="mono">{price(current)}</dd>
            </div>
            <div>
              <dt>Latent estimé</dt>
              <dd className="mono">
                {latent != null ? signedEur(latent) : '—'}
                {latentPct != null && <small> · {pct(latentPct, 1)}</small>}
              </dd>
            </div>
            <div>
              <dt>Stop / TP</dt>
              <dd className="mono">
                {price(position.stop_price)} / {price(position.take_profit_price)}
              </dd>
            </div>
          </dl>

          <p className="muted paper-confirm-note">
            La clôture réalise le P&amp;L (net frais de sortie) et libère les liquidités. Action
            irréversible sur le compte paper — pas une « vente » marché séparée.
          </p>

          <div className="paper-confirm-actions">
            <button type="button" className="ghost" disabled={confirming} onClick={handleConfirm}>
              {confirming ? 'Clôture…' : 'Confirmer la clôture'}
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
