import { labelDecision, labelPipelineGate } from '../lib/decisionLabels'
import {
  PIPELINE_STAGE_ORDER,
  stageFullLabel,
  stageMatrixLabel,
  stageStatusLabel,
  stageStatusesFromRow,
  type PipelineStageStatus,
} from '../lib/decisionPipeline'
import type { DecisionLabel, PipelineGateLabel, ScreenerDecisionRow } from '../lib/decisions'

function asGate(raw: string | undefined): PipelineGateLabel | null {
  if (raw === 'BUY' || raw === 'SELL' || raw === 'WATCH' || raw === 'NO_TRADE') return raw
  return null
}

function statusTone(status: PipelineStageStatus): string {
  switch (status) {
    case 'pass':
      return 'pass'
    case 'fail':
      return 'fail'
    case 'watch':
      return 'watch'
    case 'pending':
      return 'pending'
    case 'skip':
      return 'skip'
    default: {
      const _exhaustive: never = status
      return _exhaustive
    }
  }
}

function gateTone(gate: PipelineGateLabel | null): 'bull' | 'bear' | 'neutral' {
  if (gate === 'BUY') return 'bull'
  if (gate === 'SELL') return 'bear'
  return 'neutral'
}

function isPaperActionable(gate: PipelineGateLabel | null): boolean {
  return gate === 'BUY' || gate === 'SELL'
}

export interface GateMatrixProps {
  rows: ScreenerDecisionRow[]
  selected: string | null
  onSelect: (symbol: string) => void
  symbolLabel: (id: string) => string
  emptyHint?: string
  /** Ouvre une position paper (user_confirmed) sans passer par le Journal. */
  onOpenPaper?: (row: ScreenerDecisionRow) => void | Promise<void>
  paperBusySymbol?: string | null
  /** Symboles déjà ouverts sur le portefeuille — bouton verrouillé. */
  openPaperSymbols?: ReadonlySet<string>
}

/** Matrice portes — Option B : PORTES = seul verdict d’action ; Brut = diagnostic Ichi+RVOL. */
export function GateMatrix({
  rows,
  selected,
  onSelect,
  symbolLabel,
  emptyHint = 'Aucune ligne pour cette vue.',
  onOpenPaper,
  paperBusySymbol = null,
  openPaperSymbols,
}: GateMatrixProps) {
  if (rows.length === 0) {
    return <p className="empty muted">{emptyHint}</p>
  }

  return (
    <div className="gate-matrix-wrap">
      <table className="gate-matrix" aria-label="Matrice des portes">
        <thead>
          <tr>
            <th scope="col" className="gate-matrix-sym">
              Symbole
            </th>
            {PIPELINE_STAGE_ORDER.map((id) => (
              <th key={id} scope="col" title={stageFullLabel(id)}>
                {stageMatrixLabel(id)}
              </th>
            ))}
            <th
              scope="col"
              className="gate-matrix-verdict-head"
              title="Verdict d’action — pipeline à portes"
            >
              Portes
            </th>
            <th
              scope="col"
              className="gate-matrix-diag-head"
              title="Signal brut Ichimoku + RVOL seul — pas un verdict d’action"
            >
              Brut
            </th>
            {onOpenPaper && (
              <th scope="col" className="gate-matrix-act-head" title="Position virtuelle (pas un broker)">
                Paper
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const statuses = stageStatusesFromRow(row)
            const gate = asGate(
              typeof row.pipeline?.decision === 'string' ? row.pipeline.decision : undefined,
            )
            const active = selected === row.symbol
            const canPaper = Boolean(onOpenPaper) && isPaperActionable(gate)
            const busy = paperBusySymbol === row.symbol
            const alreadyOpen = openPaperSymbols?.has(row.symbol) === true
            const canOpen = canPaper && !busy && !alreadyOpen
            return (
              <tr
                key={row.symbol}
                className={active ? 'is-selected' : undefined}
                onClick={() => onSelect(row.symbol)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    onSelect(row.symbol)
                  }
                }}
                tabIndex={0}
                role="button"
                aria-pressed={active}
              >
                <th scope="row" className="gate-matrix-sym">
                  <span className="gate-matrix-sym-main">{symbolLabel(row.symbol)}</span>
                  <span className="muted gate-matrix-sym-id">{row.symbol}</span>
                </th>
                {PIPELINE_STAGE_ORDER.map((id) => {
                  const st = statuses[id]
                  return (
                    <td key={id}>
                      <span
                        className={`gate-matrix-pill gate-matrix-pill--${statusTone(st)}`}
                        title={`${stageFullLabel(id)} · ${stageStatusLabel(st)}`}
                      >
                        {stageStatusLabel(st)}
                      </span>
                    </td>
                  )
                })}
                <td className="gate-matrix-verdict">
                  {gate ? (
                    <span className={`bias bias-${gateTone(gate)}`}>{labelPipelineGate(gate)}</span>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
                <td className="gate-matrix-diag">
                  <span
                    className="gate-matrix-diag-label"
                    title={`Combiner legacy : ${row.decision}`}
                  >
                    {labelDecision(row.decision as DecisionLabel)}
                  </span>
                </td>
                {onOpenPaper && (
                  <td className="gate-matrix-act">
                    <button
                      type="button"
                      className="ghost gate-matrix-paper-btn"
                      disabled={!canOpen}
                      title={
                        alreadyOpen
                          ? 'Déjà une position ouverte sur ce symbole — pas de 2ᵉ achat'
                          : canPaper
                            ? 'Préparer un ordre paper (récap + confirmation)'
                            : 'Paper seulement si Portes = Achat ou Vente'
                      }
                      onClick={(e) => {
                        e.stopPropagation()
                        if (!canOpen) return
                        void onOpenPaper(row)
                      }}
                    >
                      {busy ? '…' : alreadyOpen ? 'Ouvert' : 'Vérifier…'}
                    </button>
                  </td>
                )}
              </tr>
            )
          })}
        </tbody>
      </table>
      <p className="gate-matrix-legend muted">
        <strong>Portes</strong> = verdict d’action · <strong>Brut</strong> = Ichi+RVOL (diagnostic)
        {onOpenPaper && (
          <>
            {' '}
            · <strong>Paper</strong> = virtuel si Achat/Vente
          </>
        )}{' '}
        — clic ligne = détail.
      </p>
    </div>
  )
}
