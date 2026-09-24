import type { DecisionPipelinePayload } from './decisions'

export type Interval = '15m' | '1h' | '4h' | '1d'

export interface Candle {
  time: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface IchimokuParams {
  tenkan: number
  kijun: number
  senkouB: number
  displacement: number
}

export interface VolumeParams {
  rvolLen: number
  rvolConfirm: number
  spikeMult: number
  /** Seuils moteur (pipeline / screener / backtest) — voir engine README. */
  rvolLow: number
  rvolSignificant: number
  rvolStrong: number
  rvolAnomaly: number
  atrDeadPercentile: number
  atrExtremePercentile: number
  atrStopMultiplier: number
}

export interface IchimokuPoint {
  time: number
  tenkan: number | null
  kijun: number | null
  senkouA: number | null
  senkouB: number | null
  chikou: number | null
  cloudTop: number | null
  cloudBot: number | null
  aboveCloud: boolean
  belowCloud: boolean
  cloudBullish: boolean
}

export interface VolumePoint {
  time: number
  volume: number
  volAvg: number
  rvol: number
  confirmed: boolean
  spike: boolean
  color: string
}

export type SignalKind = 'tk_long' | 'tk_short' | 'brk_long' | 'brk_short'

export interface Signal {
  time: number
  kind: SignalKind
  price: number
  rvol: number
}

export interface ScreenerRow {
  symbol: string
  price: number
  change24h: number
  quoteVolume: number
  bias: 'bull' | 'bear' | 'neutral'
  rvol: number
  signals: Signal[]
  lastSignal: Signal | null
  /** Badge moteur (si screener engine dispo pour ce symbole). */
  engineDecision?: string
  engineConfidence?: number
  /** Verdict portes (Option B) — même contrat que ScreenerDecisionRow.pipeline. */
  enginePipeline?: DecisionPipelinePayload
  /** T9f Lab snapshot (observation-only) for Contexte badges. */
  labContext?: LabContextPayload
  /** Watchlist Contexte badges (UI-MARKET). */
  context?: ContextBadge[]
}

/** Mirrors engine `lab_context` observation (T9f) — never votes BUY/SELL. */
export interface LabContextPayload {
  choch_bullish: boolean
  choch_bearish: boolean
  break_quality?: string | null
  impulse_bullish?: boolean
  impulse_bearish?: boolean
  impulse_displacement_atr?: number | null
  fvg_bullish?: boolean
  fvg_bearish?: boolean
  fvg_active: boolean
  fvg_active_bullish?: boolean
  fvg_active_bearish?: boolean
  fvg_status?: string | null
  fib_confluence: boolean
  fib_key_confluence?: boolean
  fib_impulse_up?: boolean
  fib_impulse_down?: boolean
  fib_anchor_impulse?: boolean
  fib_nearest_ratio?: number | null
  disclaimer?: string
}

export type ContextBadgeKind =
  | 'bias'
  | 'bos'
  | 'sr_break'
  | 'fvg'
  | 'fib'
  | 'choch'

export interface ContextBadge {
  kind: ContextBadgeKind
  label: string
  /** Placeholder until T9 produces data. */
  placeholder?: boolean
}


export const DEFAULT_ICHI: IchimokuParams = {
  tenkan: 9,
  kijun: 26,
  senkouB: 52,
  displacement: 26,
}

export const DEFAULT_VOL: VolumeParams = {
  rvolLen: 20,
  rvolConfirm: 1.5,
  spikeMult: 2,
  rvolLow: 0.7,
  rvolSignificant: 1.5,
  rvolStrong: 2.0,
  rvolAnomaly: 3.0,
  atrDeadPercentile: 0.15,
  atrExtremePercentile: 0.9,
  atrStopMultiplier: 1.5,
}
