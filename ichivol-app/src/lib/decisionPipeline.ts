/**
 * Contrat front du pipeline à 5 questions (north star).
 * Aujourd’hui : adapté depuis DecisionDetail (Ichimoku + RVOL).
 * Demain : le moteur pourra renvoyer `pipeline` natif — voir docs/HANDOFF-CLAUDE-PIPELINE-UI.md
 */

import type {
  AgentDirection,
  DecisionDetail,
  DecisionLabel,
  PipelineGateLabel,
} from './decisions'
import { labelDecision, labelDirection, labelPipelineGate, labelReason } from './decisionLabels'

/** Étapes product — ordre fixe du Decision Engine. */
export type PipelineStageId =
  | 'direction'
  | 'participation'
  | 'structure'
  | 'location'
  | 'regime'

export type PipelineStageStatus =
  | 'pass'
  | 'fail'
  | 'watch'
  | 'pending'
  | 'skip'

export interface PipelineStage {
  id: PipelineStageId
  question: string
  label: string
  status: PipelineStageStatus
  summary: string
  codes: string[]
  since: 'v1' | 'v1.5' | 'v2'
}

export interface DecisionPipelineView {
  symbol: string
  timeframe: string
  /** Badge / table — combiner legacy (STRONG_BUY…). Option A CDC. */
  decision: DecisionLabel
  direction: AgentDirection
  /** Verdict portes quand natif (BUY|SELL|WATCH|NO_TRADE). */
  gateDecision: PipelineGateLabel | null
  stages: PipelineStage[]
  native: boolean
  strategyVersion: string
}

/** Alias du payload API (défini aussi dans decisions.ts). */
export type NativePipelinePayload = NonNullable<DecisionDetail['pipeline']>

const STAGE_META: Record<
  PipelineStageId,
  { question: string; label: string; since: 'v1' | 'v1.5' | 'v2' }
> = {
  direction: {
    label: 'Direction',
    question: 'Où va la structure ?',
    since: 'v1',
  },
  participation: {
    label: 'Participation',
    question: 'Est-ce que ça participe ?',
    since: 'v1',
  },
  structure: {
    label: 'Structure / MTF',
    question: 'Le prix et les TF sont-ils cohérents ?',
    since: 'v1',
  },
  location: {
    label: 'Location',
    question: 'L’emplacement est-il bon ?',
    since: 'v1.5',
  },
  regime: {
    label: 'Régime / Risque',
    question: 'Est-ce tradable ? À quel risque ?',
    since: 'v1',
  },
}

export const PIPELINE_STAGE_ORDER: PipelineStageId[] = [
  'direction',
  'participation',
  'structure',
  'location',
  'regime',
]

/** Alias interne (même ordre que PIPELINE_STAGE_ORDER). */
const STAGE_ORDER = PIPELINE_STAGE_ORDER

/** Libellés courts pour en-têtes Matrice. */
export function stageMatrixLabel(id: PipelineStageId): string {
  switch (id) {
    case 'direction':
      return 'Dir'
    case 'participation':
      return 'Part'
    case 'structure':
      return 'Struct'
    case 'location':
      return 'Loc'
    case 'regime':
      return 'Régime'
    default: {
      const _exhaustive: never = id
      return _exhaustive
    }
  }
}

/**
 * Libellé cellule Matrice pour la porte Direction.
 * En `pass` : ↑ (LONG) / ↓ (SHORT) à la place de « OK » ; sinon statut classique.
 */
export function stageDirectionMatrixLabel(
  status: PipelineStageStatus,
  direction: AgentDirection | null | undefined,
): string {
  if (status === 'pass') {
    if (direction === 'LONG') return '↑'
    if (direction === 'SHORT') return '↓'
  }
  return stageStatusLabel(status)
}

export function stageFullLabel(id: PipelineStageId): string {
  return STAGE_META[id].label
}

/** Statuts par porte pour une ligne screener (pending si pipeline absent). */
export function stageStatusesFromRow(
  row: Pick<DecisionDetail, 'pipeline'>,
): Record<PipelineStageId, PipelineStageStatus> {
  const byId = new Map(row.pipeline?.stages?.map((s) => [s.id, s.status]) ?? [])
  const out = {} as Record<PipelineStageId, PipelineStageStatus>
  for (const id of PIPELINE_STAGE_ORDER) {
    out[id] = byId.get(id) ?? 'pending'
  }
  return out
}

function rvolGate(rvol: number | null): { status: PipelineStageStatus; summary: string } {
  if (rvol == null) {
    return { status: 'watch', summary: 'RVOL indisponible' }
  }
  if (rvol >= 1.5) {
    return {
      status: 'pass',
      summary: `RVOL ${rvol.toFixed(2)}× — participation confirmée (≥ 1.5)`,
    }
  }
  if (rvol >= 1.0) {
    return {
      status: 'watch',
      summary: `RVOL ${rvol.toFixed(2)}× — participation tiède (< 1.5)`,
    }
  }
  return {
    status: 'fail',
    summary: `RVOL ${rvol.toFixed(2)}× — participation insuffisante`,
  }
}

function asGateDecision(raw: string | undefined): PipelineGateLabel | null {
  if (raw === 'BUY' || raw === 'SELL' || raw === 'WATCH' || raw === 'NO_TRADE') return raw
  return null
}

/** Étapes natives → vue 5 portes (ordre fixe), utilisé par le détail ET la Matrice (CDC-VIZ-001). */
export function stagesFromNativePipeline(native: NativePipelinePayload): PipelineStage[] {
  const byId = new Map(native.stages.map((s) => [s.id, s]))
  return STAGE_ORDER.map((id) => {
    const meta = STAGE_META[id]
    const n = byId.get(id)
    if (!n) {
      return {
        id,
        ...meta,
        status: 'pending' as const,
        summary: 'En attente du moteur',
        codes: [],
      }
    }
    return {
      id,
      ...meta,
      status: n.status,
      summary: n.summary,
      codes: n.codes ?? [],
    }
  })
}

/**
 * Adapte DecisionDetail → vue 5 portes.
 * Si `detail.pipeline.stages` est présent → mode natif (Option A : badge legacy inchangé).
 */
export function pipelineFromDecisionDetail(d: DecisionDetail): DecisionPipelineView {
  const native = d.pipeline

  if (native?.stages?.length) {
    const stages = stagesFromNativePipeline(native)
    return {
      symbol: d.symbol,
      timeframe: d.timeframe,
      decision: d.decision,
      direction: (native.direction as AgentDirection | undefined) ?? d.direction,
      gateDecision: asGateDecision(native.decision),
      stages,
      native: true,
      strategyVersion: native.strategy_version ?? d.strategy_version,
    }
  }

  const dirStatus: PipelineStageStatus =
    d.ichimoku.direction === 'NEUTRAL' ? 'watch' : 'pass'
  const dirSummary =
    d.ichimoku_score != null
      ? `${labelDirection(d.ichimoku.direction)} · score ${d.ichimoku_score.toFixed(0)} · conf ${(d.ichimoku.confidence * 100).toFixed(0)}%`
      : `${labelDirection(d.ichimoku.direction)} · conf ${(d.ichimoku.confidence * 100).toFixed(0)}%`

  const part = rvolGate(d.rvol)

  const stages: PipelineStage[] = [
    {
      id: 'direction',
      ...STAGE_META.direction,
      status: dirStatus,
      summary: dirSummary,
      codes: d.ichimoku.reasons,
    },
    {
      id: 'participation',
      ...STAGE_META.participation,
      status: part.status,
      summary: part.summary,
      codes: d.rvol_detail.reasons,
    },
    {
      id: 'structure',
      ...STAGE_META.structure,
      status: 'pending',
      summary: 'Price Action + MTF — bientôt (V1 moteur)',
      codes: [],
    },
    {
      id: 'location',
      ...STAGE_META.location,
      status: 'pending',
      summary: 'Volume Profile + VWAP — V1.5',
      codes: [],
    },
    {
      id: 'regime',
      ...STAGE_META.regime,
      status: 'pending',
      summary: 'ATR / régime de volatilité — bientôt (V1 moteur)',
      codes: d.risks,
    },
  ]

  return {
    symbol: d.symbol,
    timeframe: d.timeframe,
    decision: d.decision,
    direction: d.direction,
    gateDecision: null,
    stages,
    native: false,
    strategyVersion: d.strategy_version,
  }
}

export function stageStatusLabel(status: PipelineStageStatus): string {
  switch (status) {
    case 'pass':
      return 'OK'
    case 'fail':
      return 'Bloqué'
    case 'watch':
      return 'Prudence'
    case 'pending':
      return 'Bientôt'
    case 'skip':
      return 'N/A'
    default: {
      const _exhaustive: never = status
      return _exhaustive
    }
  }
}

export function formatStageCodes(codes: string[], max = 3): string[] {
  return codes.slice(0, max).map(labelReason)
}

export function pipelineHeadline(view: DecisionPipelineView): string {
  const gate =
    view.gateDecision != null
      ? labelPipelineGate(view.gateDecision)
      : labelDecision(view.decision)
  return `${gate} · ${labelDirection(view.direction)}`
}

export interface PipelineReadingBlock {
  id: 'structure' | 'mtf' | 'location' | 'regime'
  title: string
  status: PipelineStageStatus
  body: string
  facts: string[]
}

function stageById(view: DecisionPipelineView, id: PipelineStageId): PipelineStage | undefined {
  return view.stages.find((s) => s.id === id)
}

/**
 * Cartes lisibles PA / MTF / Location / ATR — dérivées des stages natifs
 * (CDC : visibles et fiables, pas seulement codes bruts).
 */
export function pipelineReadingBlocks(view: DecisionPipelineView): PipelineReadingBlock[] {
  const structure = stageById(view, 'structure')
  const location = stageById(view, 'location')
  const regime = stageById(view, 'regime')
  const blocks: PipelineReadingBlock[] = []

  if (structure && structure.status !== 'pending') {
    const paCodes = structure.codes.filter(
      (c) => c.startsWith('structure_') || c.startsWith('bos_'),
    )
    const mtfCodes = structure.codes.filter((c) => c.startsWith('mtf_'))
    blocks.push({
      id: 'structure',
      title: 'Price Action',
      status: structure.status,
      body: structure.summary,
      facts: paCodes.length ? paCodes.map(labelReason) : [structure.summary],
    })
    blocks.push({
      id: 'mtf',
      title: 'Multi-timeframe',
      status:
        mtfCodes.includes('mtf_opposed')
          ? 'fail'
          : mtfCodes.includes('mtf_aligned')
            ? 'pass'
            : structure.status === 'skip'
              ? 'skip'
              : 'watch',
      body:
        mtfCodes.length === 0
          ? 'Alignement MTF non disponible (souvent skip hors crypto / historique court)'
          : mtfCodes.map(labelReason).join(' · '),
      facts: mtfCodes.map(labelReason),
    })
  }

  if (location && location.status !== 'pending') {
    blocks.push({
      id: 'location',
      title: 'Location (VP / VWAP)',
      status: location.status,
      body: location.summary,
      facts: location.codes.map(labelReason),
    })
  }

  if (regime && regime.status !== 'pending') {
    blocks.push({
      id: 'regime',
      title: 'Régime ATR / risque',
      status: regime.status,
      body: regime.summary,
      facts: regime.codes.map(labelReason),
    })
  }

  return blocks
}
