import { useEffect, useState } from 'react'
import { listRulesets, type RulesetSummary } from '../lib/backtest'
import type {
  BacktestOutcomeFilter,
  BacktestOverlayCounts,
  BacktestOverlayTrade,
  BacktestRejectedSignal,
  ConditionLeafTrace,
} from '../lib/backtestOverlay'

function fmtPct(n: number): string {
  return `${(n * 100).toFixed(2)} %`
}

function fmtPx(n: number): string {
  return n.toLocaleString(undefined, { maximumFractionDigits: 6 })
}

function WhyList({ title, leaves }: { title: string; leaves?: ConditionLeafTrace[] }) {
  if (!leaves || leaves.length === 0) {
    return (
      <div className="bt-why-block">
        <h3>{title}</h3>
        <p className="muted">—</p>
      </div>
    )
  }
  return (
    <div className="bt-why-block">
      <h3>{title}</h3>
      <ul className="bt-why-list">
        {leaves.map((leaf, i) => (
          <li key={`${leaf.key}-${leaf.clause}-${i}`} className={leaf.passed ? 'ok' : 'fail'}>
            <span className="bt-why-clause">{leaf.clause}</span>
            <span className="mono">
              {leaf.key}={String(leaf.expected)}
            </span>
            <span aria-label={leaf.passed ? 'ok' : 'fail'}>{leaf.passed ? '✓' : '✗'}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/**
 * T4a/T4c sheet — ruleset overlay + WHY ENTERED / EXITED / REJECTED.
 */
export function BacktestOverlaySheet({
  symbolLabel,
  selectedRulesetId,
  outcome,
  counts,
  trades,
  rejected = [],
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
  rejected?: BacktestRejectedSignal[]
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
  const [rejDetail, setRejDetail] = useState<BacktestRejectedSignal | null>(null)

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
        if (detail || rejDetail) {
          setDetail(null)
          setRejDetail(null)
        } else onClose()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose, detail, rejDetail])

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
                  <button
                    type="button"
                    onClick={() => {
                      setRejDetail(null)
                      setDetail(t)
                    }}
                  >
                    <span className={`bt-out bt-out--${t.outcome}`}>{t.outcome}</span>
                    <span>
                      #{t.trade_id} · {t.direction} · {t.exit_reason}
                    </span>
                    <span className="mono bt-ret">
                      <span className={`bt-out--${t.outcome}`}>{fmtPct(t.return_pct_net)}</span>
                      <span className="muted bt-ret-gross">brut {fmtPct(t.return_pct_gross)}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : active && !loading ? (
            <p className="muted mark-trade-hint">Aucun trade pour ce filtre.</p>
          ) : (
            <p className="muted mark-trade-hint">
              Affiche les trades sur le chart (ENTRY / STOP / TARGET + sortie) et le WHY.
            </p>
          )}

          {active && rejected.length > 0 ? (
            <>
              <p className="muted mark-trade-hint">
                Rejetés (déjà en position) : {rejected.length}
              </p>
              <ul className="backtest-trade-list" aria-label="Signaux rejetés">
                {rejected.map((r) => (
                  <li key={r.rejected_id}>
                    <button
                      type="button"
                      onClick={() => {
                        setDetail(null)
                        setRejDetail(r)
                      }}
                    >
                      <span className="bt-out bt-out--flat">rej</span>
                      <span>
                        sig#{r.signal_index} · {r.direction} · {r.reason}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          ) : null}

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
                  <dt>R (brut)</dt>
                  <dd className="mono">{detail.r_multiple_gross.toFixed(2)}</dd>
                </div>
                <div>
                  <dt>Rendement net</dt>
                  <dd className={`mono bt-out--${detail.outcome}`}>
                    {fmtPct(detail.return_pct_net)}
                  </dd>
                </div>
                <div>
                  <dt>Rendement brut</dt>
                  <dd className="mono muted">{fmtPct(detail.return_pct_gross)}</dd>
                </div>
              </dl>
              <WhyList title="WHY ENTERED" leaves={detail.why_entered} />
              <WhyList
                title={`WHY EXITED (${detail.exit_reason})`}
                leaves={
                  detail.exit_reason === 'signal'
                    ? detail.why_exited
                    : detail.why_exited && detail.why_exited.length > 0
                      ? detail.why_exited
                      : undefined
                }
              />
              {detail.exit_reason !== 'signal' ? (
                <p className="muted mark-trade-hint">
                  Sortie {detail.exit_reason} — pas de conditions DSL (stop/target/eod/max_hold).
                </p>
              ) : null}
            </div>
          ) : null}

          {rejDetail ? (
            <div className="backtest-trade-detail" role="region" aria-label="Détail rejeté">
              <header>
                <strong>Rejeté #{rejDetail.rejected_id}</strong>
                <button type="button" className="ghost" onClick={() => setRejDetail(null)}>
                  ×
                </button>
              </header>
              <dl>
                <div>
                  <dt>Raison</dt>
                  <dd>{rejDetail.reason}</dd>
                </div>
                <div>
                  <dt>Sens</dt>
                  <dd>{rejDetail.direction}</dd>
                </div>
                <div>
                  <dt>Signal bar</dt>
                  <dd className="mono">{rejDetail.signal_index}</dd>
                </div>
              </dl>
              <WhyList title="WHY aurait entré" leaves={rejDetail.why_entered} />
            </div>
          ) : null}
        </div>
      </aside>
    </div>
  )
}
