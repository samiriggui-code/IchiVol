import { useEffect, useState } from 'react'
import type { DecisionPipelineView } from '../lib/decisionPipeline'
import { getPaperPerformance, type OrderIntent } from '../lib/paper'
import {
  assetName,
  directionWords,
  EXIT_RULES,
  eur,
  hoursLabel,
  price,
  signedEur,
  stageStatusLabel,
} from '../lib/tradeStory'

function blockedText(reason: string): string {
  switch (reason) {
    case 'not_actionable':
      return 'Le moteur ne voit pas de signal d’entrée assez net (surveillance ou pas de trade). Aucun achat prévu.'
    case 'no_stop':
      return 'Le stop ne peut pas être calculé (volatilité indisponible). Sans stop, le moteur n’ouvre pas de trade.'
    case 'insufficient_cash_or_risk':
      return 'Pas assez d’argent libre ou de marge de risque dans le portefeuille pour ouvrir ce trade.'
    default:
      return reason
  }
}

/**
 * Fiche « avant d'investir » : traduit l'ordre paper proposé en langage clair
 * (combien, à quel prix, quand on sort, ce qu'IchiVol voit). Lecture seule.
 */
export function TradePlanCard({
  intent,
  pipelineView,
}: {
  intent: OrderIntent | null
  pipelineView: DecisionPipelineView | null
}) {
  const [avgHoldHours, setAvgHoldHours] = useState<number | null>(null)

  useEffect(() => {
    let alive = true
    getPaperPerformance({ source: 'auto_watchlist' })
      .then((p) => {
        if (alive) setAvgHoldHours(p.avg_holding_hours ?? null)
      })
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [])

  if (!intent) return null

  const asset = assetName(intent.symbol)
  const dir = directionWords(intent.direction)

  if (!intent.actionable || intent.qty == null || intent.notional == null) {
    return (
      <section className="trade-plan" aria-label="Plan de trade">
        <h3 className="subhead">Plan de trade · {asset}</h3>
        <p className="trade-plan-lead">{blockedText(intent.reason)}</p>
        <StagesList pipelineView={pipelineView} />
      </section>
    )
  }

  const entry = intent.entry_fill ?? intent.price
  const maxLoss =
    intent.stop_price != null ? intent.qty * Math.abs(entry - intent.stop_price) : null
  const targetGain =
    intent.take_profit_price != null
      ? intent.qty * Math.abs(intent.take_profit_price - entry)
      : null
  const share = intent.equity ? intent.notional / intent.equity : null

  return (
    <section className="trade-plan" aria-label="Plan de trade">
      <h3 className="subhead">Plan de trade · {asset}</h3>
      <p className="trade-plan-lead">
        <strong>{dir.title}</strong> de {asset} : {dir.detail}. Portefeuille virtuel{' '}
        <span className="mono">{intent.portfolio_code}</span>
        {intent.equity != null && <> ({eur(intent.equity, 0)} de valeur)</>}.
      </p>

      <dl className="trade-plan-grid">
        <div>
          <dt>Montant investi</dt>
          <dd>
            {eur(intent.notional)}
            {share != null && <small> · {(share * 100).toFixed(0)} % du capital</small>}
          </dd>
        </div>
        <div>
          <dt>Quantité</dt>
          <dd>
            {intent.qty.toPrecision(4)} {asset}
          </dd>
        </div>
        <div>
          <dt>Prix d’entrée</dt>
          <dd>
            {price(entry)}
            <small> · marché {price(intent.price)}, frais et glissement inclus</small>
          </dd>
        </div>
        <div>
          <dt>Stop (on sort si perte)</dt>
          <dd className="down">
            {price(intent.stop_price)}
            {maxLoss != null && <small> · perte max ≈ {signedEur(-maxLoss)}</small>}
          </dd>
        </div>
        <div>
          <dt>Objectif (on encaisse)</dt>
          <dd className="up">
            {price(intent.take_profit_price)}
            {targetGain != null && <small> · gain visé ≈ {signedEur(targetGain)}</small>}
          </dd>
        </div>
        <div>
          <dt>Durée de détention</dt>
          <dd>
            Pas fixée à l’avance
            <small>
              {avgHoldHours != null
                ? ` · en moyenne ${hoursLabel(avgHoldHours)} sur les trades passés`
                : ' · on garde jusqu’à une règle de sortie'}
            </small>
          </dd>
        </div>
      </dl>

      <details className="trade-plan-details" open>
        <summary>Comment ce montant est calculé</summary>
        <ol className="trade-plan-calc">
          <li>
            On accepte de risquer{' '}
            <strong>{intent.risk_pct != null ? `${(intent.risk_pct * 100).toFixed(1)} %` : '—'}</strong>{' '}
            du capital sur ce trade, soit <strong>{eur(intent.risk_amount)}</strong> au plus.
          </li>
          <li>
            Le stop est placé à une distance liée à la volatilité récente (ATR) :{' '}
            <strong>{price(intent.stop_distance)}</strong> par unité.
          </li>
          <li>
            Quantité = risque accepté ÷ distance du stop = <strong>{intent.qty.toPrecision(4)}</strong>{' '}
            {asset}, soit {eur(intent.notional)} investis. Plafonné à 25 % du capital par trade.
          </li>
          <li>Objectif placé à 2× le risque : on vise deux fois ce qu’on peut perdre.</li>
        </ol>
      </details>

      <h4 className="trade-plan-sub">Quand on vend</h4>
      <ul className="trade-plan-rules">
        {EXIT_RULES.map((r) => (
          <li key={r.title}>
            <strong>{r.title}</strong> — {r.text}
          </li>
        ))}
      </ul>

      <StagesList pipelineView={pipelineView} />

      <p className="muted trade-plan-note">
        Simulation : argent virtuel, aucun ordre réel. Les montants « € » utilisent l’USDT comme
        équivalent de l’euro. Gains et pertes affichés sont des estimations hors frais de sortie.
      </p>
    </section>
  )
}

function StagesList({ pipelineView }: { pipelineView: DecisionPipelineView | null }) {
  if (!pipelineView || pipelineView.stages.length === 0) return null
  return (
    <>
      <h4 className="trade-plan-sub">Ce qu’IchiVol voit</h4>
      <ul className="trade-plan-stages">
        {pipelineView.stages.map((s) => (
          <li key={s.id}>
            <span className={`trade-stage-status is-${s.status}`}>{stageStatusLabel(s.status)}</span>
            <span>
              <strong>{s.label}</strong> — {s.summary}
            </span>
          </li>
        ))}
      </ul>
    </>
  )
}
