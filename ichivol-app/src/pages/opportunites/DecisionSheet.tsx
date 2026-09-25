import { Link } from 'react-router-dom'
import { DecisionPipelinePanel } from '../../components/DecisionPipelinePanel'
import { ProposePaperTradePanel } from '../../components/ProposePaperTradePanel'
import { SignalEvidenceCard } from '../../components/SignalEvidenceCard'
import { TradePlanCard } from '../../components/TradePlanCard'
import { VerdictBadge } from '../../components/VerdictBadge'
import { decisionPayloadFromDetail, type AgentDecisionPayload } from '../../lib/agent'
import {
  buildDecisionSummary,
  labelDecision,
  labelPipelineGate,
} from '../../lib/decisionLabels'
import type { DecisionPipelineView } from '../../lib/decisionPipeline'
import type {
  DecisionDetail,
  PipelineGateLabel,
} from '../../lib/decisions'
import type { EngineInstrument } from '../../lib/universe'
import type { OrderIntent } from '../../lib/paper'
import { AgentBlock } from './shared'

export function DecisionSheet({
  selected,
  instrumentLabel,
  detailLoading,
  byId,
  detail,
  closeSheet,
  detailError,
  activeIntent,
  pipelineView,
  intentLoading,
  paperConfirming,
  onConfirmPaperOrder,
  onRefreshIntent,
  confirming,
  onConfirmDetail,
  explainDecision,
  compareGates,
  confirmMsg,
}: {
  selected: string
  instrumentLabel: (id: string) => string
  detailLoading: boolean
  byId: Map<string, EngineInstrument>
  detail: DecisionDetail | null
  closeSheet: () => void
  detailError: string | null
  activeIntent: OrderIntent | null
  pipelineView: DecisionPipelineView | null
  intentLoading: boolean
  paperConfirming: boolean
  onConfirmPaperOrder: () => void
  onRefreshIntent: () => void
  confirming: boolean
  onConfirmDetail: () => void
  explainDecision: (payload: AgentDecisionPayload, autoSend?: boolean) => void
  compareGates: (payload: AgentDecisionPayload, autoSend?: boolean) => void
  confirmMsg: string | null
}) {
  return (
    <aside className="panel decision-sheet" aria-label={`Détail ${selected}`}>
      <header className="panel-head decision-sheet-head">
        <div>
          <h2>{instrumentLabel(selected)}</h2>
          <span className="panel-meta">
            {detailLoading
              ? byId.get(selected)?.provider !== 'binance'
                ? 'calcul… (peut être long)'
                : 'chargement…'
              : detail
                ? `${detail.strategy_version} · ${detail.timeframe}`
                : ''}
          </span>
        </div>
        <div className="dec-sheet-head-actions">
          <Link to={`/app/market?symbol=${encodeURIComponent(selected)}`} className="ghost">
            Marché →
          </Link>
          <button
            type="button"
            className="ghost decision-sheet-close"
            onClick={closeSheet}
            aria-label="Retour à la liste"
          >
            ← Retour
          </button>
        </div>
      </header>

      <div className="decision-sheet-scroll">
        {detailError && (
          <div className="banner error" role="alert">
            {detailError}
          </div>
        )}

        {detailLoading && !detail && (
          <p className="muted decision-sheet-loading">
            Calcul du pipeline en cours
            {byId.get(selected)?.provider !== 'binance'
              ? ' — hors crypto ça peut prendre 5–20s (feed + accumulateur).'
              : '…'}
          </p>
        )}

        {detail && (
          <div className="decision-detail-body">
            <p className="dec-sheet-summary">{buildDecisionSummary(detail)}</p>

            <div className="dec-sheet-verdict">
              <VerdictBadge decision={detail.decision} pipeline={detail.pipeline} />
              {detail.pipeline?.decision && (
                <span className="muted">
                  Portes = {labelPipelineGate(detail.pipeline.decision as PipelineGateLabel)} · Brut
                  = {labelDecision(detail.decision)}
                </span>
              )}
            </div>

            <section className="dec-before-open" aria-label="Avant d’ouvrir">
              <h3 className="subhead">Avant d’ouvrir (paper)</h3>
              <TradePlanCard intent={activeIntent} pipelineView={pipelineView} />
              <ProposePaperTradePanel
                intent={activeIntent}
                loading={intentLoading || detailLoading}
                confirming={paperConfirming}
                onConfirm={() => void onConfirmPaperOrder()}
                onRefresh={() => void onRefreshIntent()}
              />
            </section>

            <div className="decision-confirm-row dec-secondary-actions">
              <button
                type="button"
                className="ghost"
                disabled={confirming}
                onClick={() => void onConfirmDetail()}
              >
                {confirming ? 'Enregistrement…' : 'Journal seulement'}
              </button>
              <button
                type="button"
                className="ghost"
                onClick={() => explainDecision(decisionPayloadFromDetail(detail))}
                title="Ouvre le Copilot avec un prompt déjà prêt"
              >
                Expliquer
              </button>
              <button
                type="button"
                className="ghost"
                onClick={() => compareGates(decisionPayloadFromDetail(detail))}
                title="Écart badge Brut vs verdict Portes"
              >
                Écart Portes / Brut
              </button>
              <span className="muted">
                Paper = position virtuelle (CTA ci-dessus) · Journal = snapshot local.
              </span>
              {confirmMsg?.startsWith('ok') ? (
                <span className="panel-meta">
                  Enregistré{confirmMsg.slice(2)} · <Link to="/app/journal">journal</Link>
                  {' · '}
                  <Link to="/app/portefeuille">synthèse</Link>
                  {' · '}
                  <Link to="/app/portefeuille?tab=positions">paper</Link>
                </span>
              ) : (
                confirmMsg && <span className="panel-meta">{confirmMsg}</span>
              )}
            </div>

            {pipelineView && (
              <details className="decision-agents-details" open>
                <summary className="subhead">Pipeline (5 portes)</summary>
                <DecisionPipelinePanel view={pipelineView} />
              </details>
            )}

            <details className="decision-agents-details">
              <summary className="subhead">Evidence &amp; preuves</summary>
              <SignalEvidenceCard detail={detail} />
            </details>

            <details className="decision-agents-details">
              <summary className="subhead">Agents bruts (Ichimoku / RVOL)</summary>
              <div className="decision-agents">
                <AgentBlock title="Ichimoku" agent={detail.ichimoku} />
                <AgentBlock title="RVOL" agent={detail.rvol_detail} />
              </div>
            </details>
          </div>
        )}
      </div>
    </aside>
  )
}
