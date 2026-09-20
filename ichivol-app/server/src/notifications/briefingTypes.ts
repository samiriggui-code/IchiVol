/** Shared payload for daily briefing email + PDF. */

export type BriefingTone = 'green' | 'red' | 'flat'

export interface BriefingKpis {
  equity: number
  initialCash: number
  cash: number
  invested: number
  totalPnl: number
  totalPnlPct: number | null
  dayChange: number | null
  dayChangePct: number | null
  unrealizedPnl: number
  realizedPnl: number
  openPositions: number
  pricedPositions: number
}

export interface BriefingPosition {
  symbol: string
  label: string
  direction: string
  timeframe: string
  notional: number
  unrealizedPnl: number | null
  unrealizedPct: number | null
  entryPrice: number | null
  currentPrice: number | null
}

export interface BriefingActivityItem {
  time: string
  title: string
  detail: string
  tone: BriefingTone
}

export interface BriefingEquityPoint {
  t: string
  equity: number
}

export interface BriefingShadow {
  nClosed: number
  meanPnlR: number | null
  filterVerdict: string | null
  plain: string
}

export interface BriefingEvidence {
  totalRows: number
  /** Lancements de collecte distincts (totalRows compte des résultats, pas des lancements). */
  runsTotal: number
  distinctDays: number
  latestPairs: number
  lastRunAt: string | null
  pipelineBeats: number
  pipelineCompared: number
  edgePlain: string
}

export interface BriefingCircuit {
  decisions24h: number
  opened24h: number
  closed24h: number
  blocked24h: number
  openNow: number
}

export interface DailyBriefing {
  portfolioCode: string
  portfolioLabel: string
  generatedAt: string
  generatedAtIso: string
  appUrl: string
  /** 2–4 sentences, desk-style. */
  headline: string
  narrative: string[]
  kpis: BriefingKpis
  equityCurve: BriefingEquityPoint[]
  /** Last ~14 closes for sparkline (oldest → newest). */
  equitySpark: number[]
  openBook: BriefingPosition[]
  tape: BriefingActivityItem[]
  shadow: BriefingShadow | null
  evidence: BriefingEvidence | null
  circuit: BriefingCircuit | null
  paperStats: {
    closedTrades: number
    winRate: number | null
    totalReturn: number | null
  } | null
}
