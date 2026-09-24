import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { PositionChart } from './PositionChart'
import { PositionScenariosDisclosure } from './ScenariosPanel'
import { getDecisionDetail, type DecisionDetail } from '../lib/decisions'
import type { PaperPosition } from '../lib/paper'
import {
  assetName,
  directionWords,
  eur,
  EXIT_RULES,
  exitReasonLabel,
  holdingLabel,
  pct,
  price,
  signedEur,
  stageStatusLabel,
} from '../lib/tradeStory'

interface SignalStage {
  id?: string | null
  status?: string | null
  summary?: string | null
}

function entryStages(p: PaperPosition): SignalStage[] {
  const raw = p.entry_signal?.stages
  return Array.isArray(raw) ? (raw as SignalStage[]) : []
}

function tone(v: number | null | undefined): string {
  if (v == null) return ''
  return v >= 0 ? 'up' : 'down'
}

/**
 * Fiche d'un trade paper : histoire chronologique (pourquoi entré, comment la taille est
 * calculée, ce qui s'est passé, pourquoi sorti). Lecture seule, données déjà en base.
 */
export function PaperTradeSheet({
  position: p,
  onClose,
}: {
  position: PaperPosition
  onClose: () => void
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const [market, setMarket] = useState<
    (DecisionDetail & { candles?: { time: number; open: number; high: number; low: number; close: number }[] }) | null
  >(null)
  const [marketErr, setMarketErr] = useState(false)

  useEffect(() => {
    let alive = true
    setMarket(null)
    setMarketErr(false)
    getDecisionDetail(p.symbol, p.timeframe, false, true)
      .then((d) => alive && setMarket(d))
      .catch(() => alive && setMarketErr(true))
    return () => {
      alive = false
    }
  }, [p.symbol, p.timeframe])

  const asset = assetName(p.symbol)
  const dir = directionWords(p.direction)
  const open = p.status === 'OPEN'
  const stages = entryStages(p)
  const entryDate = new Date(p.entry_time).toLocaleString('fr-FR')
  const exitDate = p.exit_time ? new Date(p.exit_time).toLocaleString('fr-FR') : null
  const stopDistance =
    p.stop_price != null ? Math.abs(p.entry_price - p.stop_price) : null
  const maxLoss = p.qty != null && stopDistance != null ? p.qty * stopDistance : null
  const targetGain =
    p.qty != null && p.take_profit_price != null
      ? p.qty * Math.abs(p.take_profit_price - p.entry_price)
      : null

  return (
    <div className="trade-sheet-backdrop" onClick={onClose}>
      <aside
        className="panel trade-sheet"
        aria-label={`Fiche trade ${asset}`}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="panel-head trade-sheet-head">
          <div>
            <h2>
              {dir.title} de {asset} · {p.timeframe}
            </h2>
            <span className={`propose-badge ${open ? 'is-ok' : ''}`}>
              {open ? 'EN COURS' : 'CLÔTURÉ'}
            </span>
          </div>
          <button type="button" className="ghost" onClick={onClose}>
            Fermer
          </button>
        </header>

        <div className="trade-sheet-scroll">
          <div className="trade-sheet-brief">
            <h3 className="subhead">En bref</h3>
            <p>
              {open ? (
                <>
                  Position <strong>encore ouverte</strong> : {dir.title.toLowerCase()} de{' '}
                  <strong>{asset}</strong> depuis le {entryDate}, à {price(p.entry_price)}.
                  {p.notional != null && (
                    <> Environ <strong>{eur(p.notional)}</strong> investis.</>
                  )}{' '}
                  On gagne si le prix {p.direction === 'LONG' ? 'monte' : 'baisse'} ; on sort au
                  stop ({price(p.stop_price)}) ou à l’objectif ({price(p.take_profit_price)}).
                </>
              ) : (
                <>
                  Trade <strong>terminé</strong> le {exitDate ?? '—'}. {dir.title} de{' '}
                  <strong>{asset}</strong> : résultat{' '}
                  <strong className={tone(p.realized_pnl)}>{signedEur(p.realized_pnl)}</strong>
                  {' — '}
                  {exitReasonLabel(p.exit_reason)}.
                </>
              )}
            </p>
            <p className="muted">
              {dir.detail}. Origine :{' '}
              {p.source === 'auto_watchlist'
                ? 'le screener a ouvert tout seul'
                : 'vous avez confirmé depuis Décisions'}
              .
            </p>
          </div>

          <dl className="trade-plan-grid">
            <div>
              <dt>Montant investi</dt>
              <dd>{eur(p.notional)}</dd>
            </div>
            <div>
              <dt>Quantité</dt>
              <dd>{p.qty != null ? `${p.qty.toPrecision(4)} ${asset}` : '—'}</dd>
            </div>
            <div>
              <dt>{open ? 'Résultat (réalisé / restant)' : 'Résultat final'}</dt>
              <dd className={tone(open ? (p.partial_exits?.length ? p.realized_pnl : null) : p.realized_pnl)}>
                {open ? (
                  (p.partial_exits?.length ?? 0) > 0 ? (
                    <>
                      {signedEur(p.realized_pnl)}
                      <small> · prises partielles</small>
                    </>
                  ) : (
                    'pas encore réalisé'
                  )
                ) : (
                  <>
                    {signedEur(p.realized_pnl)}
                    <small> · {pct(p.pnl_pct, 2)}</small>
                  </>
                )}
              </dd>
            </div>
            <div>
              <dt>Durée</dt>
              <dd>{holdingLabel(p.entry_time, p.exit_time)}</dd>
            </div>
          </dl>

          {open && <PositionScenariosDisclosure positionId={p.id} />}

          <h3 className="subhead">Le marché maintenant</h3>
          {marketErr && <p className="muted">Données de marché indisponibles pour le moment.</p>}
          {!market && !marketErr && <p className="muted">Chargement du graphique et des indicateurs…</p>}
          {market && (
            <div className="trade-market">
              <PositionChart
                candles={market.candles ?? []}
                entry={p.entry_price}
                stop={p.stop_price}
                target={p.take_profit_price}
                exit={p.exit_price}
              />
              <dl className="trade-plan-grid">
                <div>
                  <dt>Prix actuel</dt>
                  <dd>{price(market.price)}</dd>
                </div>
                <div>
                  <dt>Verdict actuel d’IchiVol</dt>
                  <dd>
                    {market.pipeline?.decision ?? market.decision}
                    <small> · confiance {(market.confidence * 100).toFixed(0)} %</small>
                  </dd>
                </div>
                <div>
                  <dt>Tendance (Ichimoku)</dt>
                  <dd>
                    {market.ichimoku.direction}
                    <small> · confiance {(market.ichimoku.confidence * 100).toFixed(0)} %</small>
                  </dd>
                </div>
                <div>
                  <dt>Participation (RVOL)</dt>
                  <dd>
                    {market.rvol != null ? `${market.rvol.toFixed(2)}×` : '—'}
                    <small> · volume relatif à la normale</small>
                  </dd>
                </div>
              </dl>
              {market.reasons.length > 0 && (
                <>
                  <h4 className="trade-plan-sub">Pourquoi</h4>
                  <ul className="trade-plan-rules">
                    {market.reasons.slice(0, 6).map((r) => (
                      <li key={r}>{r}</li>
                    ))}
                  </ul>
                </>
              )}
              {(market.risks.length > 0 || market.invalidation.length > 0) && (
                <>
                  <h4 className="trade-plan-sub">Risques et ce qui invaliderait le scénario</h4>
                  <ul className="trade-plan-rules">
                    {[...market.risks, ...market.invalidation].slice(0, 6).map((r) => (
                      <li key={r}>{r}</li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          )}

          <h3 className="subhead">L’histoire du trade</h3>
          <ol className="trade-timeline">
            <li>
              <h4>1 · Entrée — {entryDate}</h4>
              <p>
                IchiVol a jugé le signal exploitable ({p.entry_decision}) et a {dir.title.toLowerCase()}{' '}
                à <strong>{price(p.entry_price)}</strong>. Origine :{' '}
                {p.source === 'auto_watchlist' ? 'ouverture automatique (screener)' : 'confirmée par vous'}.
              </p>
              {stages.length > 0 && (
                <ul className="trade-plan-stages">
                  {stages.map((s, i) => (
                    <li key={`${s.id ?? i}`}>
                      <span className={`trade-stage-status is-${(s.status ?? '').toLowerCase()}`}>
                        {stageStatusLabel(s.status)}
                      </span>
                      <span>
                        <strong>{s.id ?? 'étape'}</strong>
                        {s.summary ? ` — ${s.summary}` : ''}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              {(p.decision_id || p.evidence_id) && (
                <p>
                  <Link to={`/app/decisions?symbol=${encodeURIComponent(p.symbol)}`}>
                    Revoir la décision et l’evidence d’origine
                  </Link>
                </p>
              )}
            </li>

            <li>
              <h4>2 · Taille de la position</h4>
              <p>
                Risque accepté : <strong>{eur(p.risk_amount)}</strong>
                {p.risk_pct != null && <> ({(p.risk_pct * 100).toFixed(1)} % du capital)</>}. Distance
                du stop : {price(stopDistance)} par unité. Quantité = risque ÷ distance du stop ={' '}
                <strong>{p.qty != null ? p.qty.toPrecision(4) : '—'}</strong>, soit{' '}
                <strong>{eur(p.notional)}</strong> investis.
              </p>
            </li>

            <li>
              <h4>3 · Protections fixées à l’entrée</h4>
              <p>
                Stop : <strong className="down">{price(p.stop_price)}</strong>
                {maxLoss != null && <> (perte max ≈ {signedEur(-maxLoss)})</>}. Objectif :{' '}
                <strong className="up">{price(p.take_profit_price)}</strong>
                {targetGain != null && <> (gain visé ≈ {signedEur(targetGain)})</>}.
              </p>
            </li>

            {(p.partial_exits?.length ?? 0) > 0 && (
              <li>
                <h4>3b · Prises partielles</h4>
                <ul className="trade-plan-rules">
                  {p.partial_exits!.map((pe) => (
                    <li key={pe.seq}>
                      {pe.r_multiple}R · {(pe.fraction * 100).toFixed(0)} % · qty{' '}
                      {pe.qty.toPrecision(4)} @ {price(pe.price)} →{' '}
                      <span className={tone(pe.realized_pnl)}>{signedEur(pe.realized_pnl)}</span>
                    </li>
                  ))}
                </ul>
                {open && p.qty != null && (
                  <p className="muted">Quantité restante : {p.qty.toPrecision(4)} {asset}.</p>
                )}
              </li>
            )}

            <li>
              <h4>4 · Évolution pendant le trade</h4>
              <p>
                Meilleur moment : <strong className="up">{pct(p.mfe_pct, 2)}</strong> · pire moment :{' '}
                <strong className="down">{pct(p.mae_pct, 2)}</strong> (par rapport au prix d’entrée).
                {open && ' Le trade est toujours ouvert : ces valeurs évoluent.'}
              </p>
            </li>

            <li>
              <h4>5 · Sortie{exitDate ? ` — ${exitDate}` : ''}</h4>
              {open ? (
                <p>
                  Pas encore vendu. On sort si le stop ou l’objectif est touché, si le signal se
                  retourne ou s’affaiblit, ou si vous fermez manuellement.
                </p>
              ) : (
                <p>
                  Vendu à <strong>{price(p.exit_price)}</strong>. Raison :{' '}
                  <strong>{exitReasonLabel(p.exit_reason)}</strong>. Résultat :{' '}
                  <strong className={tone(p.realized_pnl)}>{signedEur(p.realized_pnl)}</strong> (
                  {pct(p.pnl_pct, 2)}).
                </p>
              )}
            </li>
          </ol>

          <h3 className="subhead">Rappels : comment on sort</h3>
          <ul className="trade-plan-rules">
            {EXIT_RULES.map((r) => (
              <li key={r.title}>
                <strong>{r.title}.</strong> {r.text}
              </li>
            ))}
          </ul>

          <p className="muted trade-plan-note">
            Simulation : argent virtuel, aucun ordre réel. Montants en € (USDT utilisé comme
            équivalent).
          </p>
        </div>
      </aside>
    </div>
  )
}
