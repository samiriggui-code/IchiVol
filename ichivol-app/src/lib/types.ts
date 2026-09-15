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
}

export const COLORS = {
  bull: '#2DD4BF',
  bear: '#F07167',
  neutral: '#E8B86D',
  weak: '#5B6B73',
  ink: '#0B1215',
  panel: '#121A1E',
  line: '#1E2A30',
  text: '#E7EEF0',
  muted: '#8AA0A8',
  tenkan: '#F4A261',
  kijun: '#7EB8DA',
  spanA: '#2DD4BF',
  spanB: '#F07167',
} as const
