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
