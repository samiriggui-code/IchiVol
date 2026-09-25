import {
  labelDirection,
  labelReason,
} from '../../lib/decisionLabels'
import {
  type DecisionLabel,
  type PipelineGateLabel,
  type ScreenerDecisionRow,
  type AgentDetail,
} from '../../lib/decisions'
import type { EngineAssetClass, EngineInstrument } from '../../lib/universe'
import type { OrderIntent } from '../../lib/paper'

export type SortKey = 'symbol' | 'decision' | 'confidence' | 'ichimoku_score' | 'rvol' | 'price'
export type SortDir = 'asc' | 'desc'
export type ListView = 'liste' | 'matrice'

export const CLASS_ORDER: EngineAssetClass[] = [
  'crypto',
  'forex',
  'metal',
  'index',
  'equity',
  'energy',
]

/** Equity Twelve Data : hors cache screener (crédits) — lignes locales, détail au clic. */
export function placeholderRow(inst: EngineInstrument): ScreenerDecisionRow {
  return {
    symbol: inst.id,
    timeframe: '1h',
    price: 0,
    decision: 'WAIT',
    direction: 'NEUTRAL',
    confidence: 0,
    probability: 0,
    ichimoku_score: null,
    rvol: null,
  }
}

export const DECISION_FILTERS: Array<'all' | DecisionLabel> = [
  'all',
  'STRONG_BUY',
  'BUY',
  'WATCH',
  'WAIT',
  'SELL',
  'STRONG_SELL',
]

export const DECISION_RANK: Record<DecisionLabel, number> = {
  STRONG_BUY: 6,
  BUY: 5,
  WATCH: 4,
  WAIT: 3,
  SELL: 2,
  STRONG_SELL: 1,
}

export const GATE_RANK: Record<PipelineGateLabel, number> = {
  BUY: 4,
  SELL: 3,
  WATCH: 2,
  NO_TRADE: 1,
}

export function rowGate(r: ScreenerDecisionRow): PipelineGateLabel | null {
  const raw = r.pipeline?.decision
  if (raw === 'BUY' || raw === 'SELL' || raw === 'WATCH' || raw === 'NO_TRADE') return raw
  return null
}

export function fmtCacheAge(seconds: number): string {
  if (seconds < 5) return 'à l’instant'
  if (seconds < 60) return `il y a ${Math.floor(seconds)}s`
  return `il y a ${Math.floor(seconds / 60)}min`
}

export function ReasonChips({ codes, risk }: { codes: string[]; risk?: boolean }) {
  return (
    <div className="chip-row">
      {codes.map((code) => (
        <span key={code} className={`sig-chip${risk ? ' risk-chip' : ''}`} title={code}>
          {labelReason(code)}
        </span>
      ))}
    </div>
  )
}

export function AgentBlock({ title, agent }: { title: string; agent: AgentDetail }) {
  return (
    <div className="decision-agent">
      <div className="decision-agent-head">
        <strong>{title}</strong>
        <span className="muted">
          {labelDirection(agent.direction)} · {(agent.confidence * 100).toFixed(0)}%
        </span>
      </div>
      {agent.reasons.length > 0 && <ReasonChips codes={agent.reasons} />}
    </div>
  )
}

export function sortMarker(active: boolean, dir: SortDir): string {
  if (!active) return ''
  return dir === 'asc' ? ' ↑' : ' ↓'
}

export function compareRows(a: ScreenerDecisionRow, b: ScreenerDecisionRow, key: SortKey, dir: SortDir): number {
  const mul = dir === 'asc' ? 1 : -1
  switch (key) {
    case 'symbol':
      return mul * a.symbol.localeCompare(b.symbol)
    case 'decision': {
      const ga = rowGate(a)
      const gb = rowGate(b)
      if (ga && gb) return mul * (GATE_RANK[ga] - GATE_RANK[gb])
      if (ga) return mul * 1
      if (gb) return mul * -1
      return mul * (DECISION_RANK[a.decision] - DECISION_RANK[b.decision])
    }
    case 'confidence':
      return mul * (a.confidence - b.confidence)
    case 'ichimoku_score': {
      const av = a.ichimoku_score ?? Number.NEGATIVE_INFINITY
      const bv = b.ichimoku_score ?? Number.NEGATIVE_INFINITY
      return mul * (av - bv)
    }
    case 'rvol': {
      const av = a.rvol ?? Number.NEGATIVE_INFINITY
      const bv = b.rvol ?? Number.NEGATIVE_INFINITY
      return mul * (av - bv)
    }
    case 'price':
      return mul * (a.price - b.price)
    default: {
      const _exhaustive: never = key
      return _exhaustive
    }
  }
}

export type PaperConfirmState = {
  symbol: string
  timeframe: string
  intent: OrderIntent | null
  source: 'sheet' | 'matrix'
}
