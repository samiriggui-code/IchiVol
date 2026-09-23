import { useEffect, useState } from 'react'
import { listRulesets, type RulesetSummary } from '../lib/backtest'
import type {
  BacktestOutcomeFilter,
  BacktestOverlayCounts,
  BacktestOverlayTrade,
} from '../lib/backtestOverlay'

function fmtPct(n: number): string {
  return `${(n * 100).toFixed(2)} %`
}

function fmtPx(n: number): string {
  return n.toLocaleString(undefined, { maximumFractionDigits: 6 })
}

/**
 * T4a sheet — pick a catalog ruleset, Afficher / Effacer, filter win/loss, tap trade detail.
 */
export function BacktestOverlaySheet({
  symbolLabel,
  selectedRulesetId,
  outcome,
  counts,
  trades,
  loading,
  error,
  active,
  onSelectRuleset,
  onOutcome,
  onShow,
  onClear,
  onClose,
}: {
  symbolLabel: string
  selectedRulesetId: string | null
  outcome: BacktestOutcomeFilter
  counts: BacktestOverlayCounts | null
  trades: BacktestOverlayTrade[]
  loading?: boolean
  error?: string | null
  active: boolean
  onSelectRuleset: (id: string) => void
  onOutcome: (o: BacktestOutcomeFilter) => void
  onShow: () => void
  onClear: () => void
  onClose: () => void
}) {
  const [rulesets, setRulesets] = useState<RulesetSummary[]>([])
  const [listErr, setListErr] = useState<string | null>(null)
  const [detail, setDetail] = useState<BacktestOverlayTrade | null>(null)

  useEffect(() => {
    let cancelled = false
    listRulesets()
      .then((r) => {
        if (!cancelled) setRulesets(r.rulesets)
      })
      .catch((e: unknown) => {
        if (!cancelled) setListErr(e instanceof Error ? e.message : 'Catalogue indisponible')
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (detail) setDetail(null)
        else onClose()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose, detail])

  return (
    <div className="mark-trade-backdrop" role="presentation">
      <aside
        className="mark-trade-sheet decision-sheet backtest-overlay-sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby="bt-overlay-title"
      >
        <header className="decision-sheet-head mark-trade-head">
          <div>
            <p className="muted mark-trade-eyebrow">Backtest</p>
            <h2 id="bt-overlay-title">{symbolLabel}</h2>
          </div>
          <button type="button" className="ghost decision-sheet-close" onClick={onClose}>
            Fermer
          </button>
        </header>

        <div className="decision-sheet-scroll mark-trade-body">
          <label className="backtest-overlay-select">
            Stratégie
            <select
              value={selectedRulesetId ?? ''}
              onChange={(e) => onSelectRuleset(e.target.value)}
              disabled={loading}
            >
              <option value="" disabled>
                Choisir…
              </option>
              {rulesets.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.id}
                </option>
              ))}
            </select>
          </label>

          <div className="mark-trade-actions">
            <button
              type="button"
              className="mark-trade-validate"
              disabled={!selectedRulesetId || loading}
              onClick={onShow}
            >
              {loading ? 'Calcul…' : 'Afficher'}
            </button>
            <button type="button" className="ghost" disabled={!active || loading} onClick={onClear}>
              Effacer
            </button>
          </div>

          {counts ? (
            <div className="backtest-outcome-toggle" role="group" aria-label="Filtre résultat">
              {(
                [
                  ['all', 'Tous', counts.total],
                  ['win', 'Gagnants', counts.win],
                  ['loss', 'Perdants', counts.loss],
                ] as const
              ).map(([key, label, n]) => (
                <button
                  key={key}
                  type="button"
                  className={outcome === key ? 'is-on' : undefined}
                  onClick={() => onOutcome(key)}
                  disabled={loading}
                >
                  {label} ({n})
                </button>
              ))}
            </div>
          ) : null}

          {listErr || error ? (
            <div className="banner error" role="alert">
              {error ?? listErr}
            </div>
          ) : null}

          {active && trades.length > 0 ? (
            <ul className="backtest-trade-list" aria-label="Trades">
              {trades.map((t) => (
                <li key={t.trade_id}>
                  <button type="button" onClick={() => setDetail(t)}>
                    <span className={`bt-out bt-out--${t.outcome}`}>{t.outcome}</span>
                    <span>
                      #{t.trade_id} · {t.direction} · {t.exit_reason}
                    </span>
                    <span className="mono">{fmtPct(t.return_pct)}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : active && !loading ? (
            <p className="muted mark-trade-hint">Aucun trade pour ce filtre.</p>
          ) : (
            <p className="muted mark-trade-hint">
              Affiche les trades sur le chart (ENTRY / STOP / TARGET + sortie).
            </p>
          )}

          {detail ? (
            <div className="backtest-trade-detail" role="region" aria-label="Détail trade">
              <header>
                <strong>Trade #{detail.trade_id}</strong>
                <button type="button" className="ghost" onClick={() => setDetail(null)}>
                  ×
                </button>
              </header>
              <dl>
                <div>
                  <dt>Sens</dt>
                  <dd>{detail.direction}</dd>
                </div>
                <div>
                  <dt>Entrée</dt>
                  <dd className="mono">{fmtPx(detail.entry_price)}</dd>
                </div>
                <div>
                  <dt>Sortie</dt>
                  <dd className="mono">{fmtPx(detail.exit_price)}</dd>
                </div>
                <div>
                  <dt>Raison</dt>
                  <dd>{detail.exit_reason}</dd>
                </div>
                <div>
                  <dt>R</dt>
                  <dd className="mono">{detail.r_multiple.toFixed(2)}</dd>
                </div>
                <div>
                  <dt>Rendement</dt>
                  <dd className={`mono bt-out--${detail.outcome}`}>{fmtPct(detail.return_pct)}</dd>
                </div>
              </dl>
            </div>
          ) : null}
        </div>
      </aside>
    </div>
  )
}
