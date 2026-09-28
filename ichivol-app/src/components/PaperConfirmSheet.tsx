import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { labelPipelineGate } from '../lib/decisionLabels'
import type { PipelineGateLabel } from '../lib/decisions'
import {
  previewPaperBuy,
  type ManualOrderInput,
  type ManualPreview,
  type OrderIntent,
} from '../lib/paper'
import { eur, price as fmtPrice, signedEur } from '../lib/tradeStory'
import { ScenariosPanel } from './ScenariosPanel'

const AMOUNT_CHIPS = [100, 250, 500, 1000]
const STOP_CHIPS = [0.01, 0.02, 0.03, 0.05]
const TARGET_CHIPS = [1.5, 2, 3]

function num(v: string): number {
  const n = Number(v.replace(/\s/g, '').replace(',', '.'))
  return Number.isFinite(n) ? n : NaN
}

/**
 * Ticket d'ordre paper : acheter ou ajouter une ligne au portefeuille.
 * Vous choisissez le montant, le stop et l'objectif ; le moteur vous montre AVANT de confirmer
 * les frais, le gain et la perte nets et l'effet sur le portefeuille. Un avis du moteur (Achat /
 * Attente) est affiché mais ne bloque pas votre choix — seules les limites de sécurité du compte le font,
 * avec le motif. Virtuel : aucun broker réel.
 */
export function PaperConfirmSheet({
  symbol,
  timeframe,
  symbolLabel,
  intent,
  confirming,
  error,
  onConfirm,
  onCancel,
}: {
  symbol: string
  timeframe: string
  symbolLabel: string
  /** Proposition du moteur (taille suggérée). Peut être absente ou non actionnable. */
  intent: OrderIntent | null
  confirming?: boolean
  error?: string | null
  onConfirm: (order: ManualOrderInput) => void
  onCancel: () => void
}) {
  const clickLock = useRef(false)
  const suggested =
    intent?.actionable && intent.notional ? Math.round(intent.notional / 10) * 10 || intent.notional : null
  const suggestedStop =
    intent?.stop_distance && intent.price ? Math.min(0.3, Math.max(0.005, intent.stop_distance / intent.price)) : null

  const [amount, setAmount] = useState<string>(String(suggested ?? 250))
  const [stopPct, setStopPct] = useState<number>(suggestedStop ?? 0.02)
  const [tpR, setTpR] = useState<number>(2)
  const [preview, setPreview] = useState<ManualPreview | null>(null)
  const [previewErr, setPreviewErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const notional = num(amount)
  const valid = Number.isFinite(notional) && notional > 0

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

  // Aperçu recalculé à chaque changement (léger délai), jamais d'ordre placé.
  useEffect(() => {
    if (!valid) {
      setPreview(null)
      return
    }
    const ctrl = new AbortController()
    setLoading(true)
    const t = window.setTimeout(() => {
      previewPaperBuy(symbol, timeframe, { notional, stopPct, takeProfitR: tpR }, ctrl.signal)
        .then((p) => {
          setPreview(p)
          setPreviewErr(null)
        })
        .catch((e: unknown) => {
          if (ctrl.signal.aborted) return
          setPreview(null)
          setPreviewErr(e instanceof Error ? e.message : 'Aperçu indisponible')
        })
        .finally(() => {
          if (!ctrl.signal.aborted) setLoading(false)
        })
    }, 250)
    return () => {
      window.clearTimeout(t)
      ctrl.abort()
    }
  }, [symbol, timeframe, notional, stopPct, tpR, valid])

  const cash = preview?.portfolio.cash_before ?? intent?.cash ?? null
  const chips = useMemo(() => {
    const out = [...AMOUNT_CHIPS]
    if (cash && cash > 0) {
      const all = Math.floor(cash / 1.01)
      if (all >= 10 && !out.includes(all)) out.push(all)
    }
    return out
  }, [cash])

  const ok = Boolean(preview?.ok) && valid && !loading
  const verdict = preview?.engine_verdict ?? intent?.pipeline_decision
  const isBuy = verdict === 'BUY'
  const verdictLabel = verdict ? labelPipelineGate(verdict as PipelineGateLabel) || verdict : '—'

  function handleConfirm() {
    if (confirming || clickLock.current || !ok) return
    clickLock.current = true
    onConfirm({ notional, stopPct, takeProfitR: tpR })
  }

  return (
    <div
      className="trade-sheet-backdrop paper-confirm-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label={`Acheter ${symbolLabel} en paper`}
      onClick={(e) => {
        if (e.target === e.currentTarget && !confirming) onCancel()
      }}
    >
      <aside className="panel trade-sheet paper-confirm-sheet order-ticket">
        <header className="panel-head trade-sheet-head">
          <div>
            <h2>Acheter · {symbolLabel}</h2>
            <p className="muted">
              Paper · virtuel, aucun broker réel
              {preview && ` · px ${fmtPrice(preview.price)}`}
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

          <div className={`ot-engine-card${isBuy ? ' is-buy' : ' is-hold'}`}>
            <div className="ot-engine-card-top">
              <span className="ot-engine-kicker">Avis du moteur · Decision Engine</span>
              <span className={`ot-engine-badge${isBuy ? ' is-buy' : ' is-hold'}`}>{verdictLabel}</span>
            </div>
            <p className="ot-engine-copy">
              {isBuy
                ? 'Le pipeline recommande un achat ici. Vous restez libre de confirmer ou non.'
                : 'Pas de trade recommandé — vous pouvez acheter quand même, c’est votre décision.'}
            </p>
          </div>

          <section className="ot-card">
            <h3 className="ot-card-title">Combien investir ?</h3>
            <div className="order-input-row">
              <input
                className="order-input mono"
                inputMode="decimal"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                aria-label="Montant en euros"
              />
              <span className="muted">€</span>
              {suggested && (
                <button type="button" className="ghost order-chip" onClick={() => setAmount(String(suggested))}>
                  Moteur · {eur(suggested, 0)}
                </button>
              )}
            </div>
            <div className="order-chips">
              {chips.map((c) => (
                <button
                  type="button"
                  key={c}
                  className={`ghost order-chip${notional === c ? ' is-on' : ''}`}
                  onClick={() => setAmount(String(c))}
                >
                  {c === chips[chips.length - 1] && !AMOUNT_CHIPS.includes(c) ? `Tout · ${eur(c, 0)}` : eur(c, 0)}
                </button>
              ))}
            </div>
          </section>

          <section className="ot-card ot-card--split">
            <div>
              <h3 className="ot-card-title">Stop (perte max)</h3>
              <div className="order-chips">
                {STOP_CHIPS.map((s) => (
                  <button
                    type="button"
                    key={s}
                    className={`ghost order-chip${Math.abs(stopPct - s) < 1e-6 ? ' is-on' : ''}`}
                    onClick={() => setStopPct(s)}
                  >
                    {(s * 100).toFixed(0)} %
                  </button>
                ))}
                {suggestedStop && (
                  <button
                    type="button"
                    className={`ghost order-chip${Math.abs(stopPct - suggestedStop) < 1e-6 ? ' is-on' : ''}`}
                    onClick={() => setStopPct(suggestedStop)}
                    title="Distance calculée par le moteur (volatilité ATR)"
                  >
                    Moteur · {(suggestedStop * 100).toFixed(1)} %
                  </button>
                )}
              </div>
            </div>
            <div>
              <h3 className="ot-card-title">Objectif (R multiple)</h3>
              <div className="order-chips">
                {TARGET_CHIPS.map((r) => (
                  <button
                    type="button"
                    key={r}
                    className={`ghost order-chip${tpR === r ? ' is-on' : ''}`}
                    onClick={() => setTpR(r)}
                  >
                    {r} ×
                  </button>
                ))}
              </div>
            </div>
          </section>

          {loading && <p className="muted">Calcul en cours…</p>}
          {previewErr && (
            <div className="banner error" role="alert">
              {previewErr}
            </div>
          )}
          {!valid && <p className="muted">Entrez un montant en euros.</p>}

          {preview && (
            <>
              {preview.blocking.map((b) => (
                <div className="banner error" role="alert" key={b.code}>
                  {b.message}
                </div>
              ))}
              {preview.warnings.map((w) => (
                <div className="banner warn" key={w.code}>
                  {w.message}
                </div>
              ))}

              <div className="order-outcomes">
                <div className="order-outcome order-outcome--gain">
                  <span className="ot-outcome-label">Si objectif</span>
                  <strong className="mono up">{signedEur(preview.outcomes.net_gain_if_target)}</strong>
                  <span className="muted mono">@ {fmtPrice(preview.order.take_profit_price)} · net frais</span>
                </div>
                <div className="order-outcome order-outcome--loss">
                  <span className="ot-outcome-label">Si stop</span>
                  <strong className="mono down">{signedEur(preview.outcomes.net_loss_if_stop)}</strong>
                  <span className="muted mono">@ {fmtPrice(preview.order.stop_price)} · frais inclus</span>
                </div>
              </div>

              <ScenariosPanel scenarios={preview.scenarios} variant="preview" />

              <section className="ot-card">
                <h3 className="ot-card-title">Détail de l’ordre</h3>
                <dl className="ot-kv">
                  <div>
                    <dt>Vous achetez</dt>
                    <dd className="mono">
                      {preview.order.qty.toPrecision(5)} · {eur(preview.order.notional)}
                    </dd>
                  </div>
                  <div>
                    <dt>Prix d’exécution</dt>
                    <dd className="mono">{fmtPrice(preview.order.entry_fill)}</dd>
                  </div>
                  <div>
                    <dt>Commission entrée</dt>
                    <dd className="mono">
                      {eur(preview.costs.commission_entry)} ({preview.costs.commission_bps} bps)
                    </dd>
                  </div>
                  <div>
                    <dt>Écart + glissement</dt>
                    <dd className="mono">
                      {eur(preview.costs.spread_slippage_entry)} ({preview.costs.friction_bps_per_side} bps)
                    </dd>
                  </div>
                  <div>
                    <dt>Frais A/R</dt>
                    <dd className="mono">{eur(preview.costs.round_trip_at_target)}</dd>
                  </div>
                  <div>
                    <dt>Risque jusqu’au stop</dt>
                    <dd className="mono">
                      {eur(preview.order.risk_amount)}
                      {preview.order.risk_pct_of_equity != null &&
                        ` (${(preview.order.risk_pct_of_equity * 100).toFixed(2)} % cap.)`}
                    </dd>
                  </div>
                </dl>
              </section>

              <section className="ot-card ot-card--portfolio">
                <h3 className="ot-card-title">Effet portefeuille</h3>
                <div className="ot-portfolio-row">
                  <span>Liquidités</span>
                  <span className="mono">
                    {eur(preview.portfolio.cash_before)} → <strong>{eur(preview.portfolio.cash_after)}</strong>
                  </span>
                </div>
                <div className="ot-portfolio-row">
                  <span>Lignes</span>
                  <span className="mono">
                    {preview.portfolio.lines_before} → {preview.portfolio.lines_after} / {preview.portfolio.max_lines}
                  </span>
                </div>
                {preview.portfolio.open_risk_cap != null && (
                  <div className="ot-portfolio-row">
                    <span>Risque cumulé</span>
                    <span className="mono">
                      {eur(preview.portfolio.open_risk_after, 0)} / {eur(preview.portfolio.open_risk_cap, 0)}
                    </span>
                  </div>
                )}
              </section>
            </>
          )}

          <p className="muted paper-confirm-note">
            Un lot par marché. Vente depuis{' '}
            <Link to="/app/portefeuille">Portefeuille</Link> · <Link to="/app/journal">Journal</Link>.
          </p>

          <div className="paper-confirm-actions">
            <button type="button" className="ghost order-confirm" disabled={!ok || confirming} onClick={handleConfirm}>
              {confirming ? 'Ouverture…' : `Confirmer l’achat · ${valid ? eur(notional, 0) : '—'}`}
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
