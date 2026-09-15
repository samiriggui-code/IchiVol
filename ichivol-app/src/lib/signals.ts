import { computeIchimoku } from './ichimoku'
import {
  COLORS,
  type Candle,
  type IchimokuParams,
  type Signal,
  type SignalKind,
  type VolumeParams,
  type VolumePoint,
} from './types'

export function computeVolumePulse(
  candles: Candle[],
  ichiParams: IchimokuParams,
  volParams: VolumeParams,
): { volumes: VolumePoint[]; signals: Signal[] } {
  const ichi = computeIchimoku(candles, ichiParams)
  const { rvolLen, rvolConfirm, spikeMult } = volParams
  const volumes: VolumePoint[] = []
  const signals: Signal[] = []

  for (let i = 0; i < candles.length; i++) {
    const c = candles[i]
    const ip = ichi[i]
    let sum = 0
    let count = 0
    for (let j = Math.max(0, i - rvolLen + 1); j <= i; j++) {
      sum += candles[j].volume
      count++
    }
    const volAvg = count > 0 ? sum / count : 0
    const rvol = volAvg > 0 ? c.volume / volAvg : 0
    const confirmed = rvol >= rvolConfirm
    const spike = rvol >= spikeMult

    let color: string = COLORS.weak
    if (c.volume >= volAvg) {
      if (ip.aboveCloud) color = spike ? COLORS.bull : `${COLORS.bull}99`
      else if (ip.belowCloud) color = spike ? COLORS.bear : `${COLORS.bear}99`
      else color = spike ? COLORS.neutral : `${COLORS.neutral}99`
    }

    volumes.push({
      time: c.time,
      volume: c.volume,
      volAvg,
      rvol,
      confirmed,
      spike,
      color,
    })
  }

  for (let i = 1; i < candles.length; i++) {
    const v = volumes[i]
    if (!v.confirmed) continue
    const ip = ichi[i]
    const prev = ichi[i - 1]
    const c = candles[i]
    const pc = candles[i - 1]

    const tkUp =
      ip.tenkan != null &&
      ip.kijun != null &&
      prev.tenkan != null &&
      prev.kijun != null &&
      prev.tenkan <= prev.kijun &&
      ip.tenkan > ip.kijun
    const tkDn =
      ip.tenkan != null &&
      ip.kijun != null &&
      prev.tenkan != null &&
      prev.kijun != null &&
      prev.tenkan >= prev.kijun &&
      ip.tenkan < ip.kijun

    if (tkUp && ip.aboveCloud) {
      signals.push({ time: c.time, kind: 'tk_long', price: c.close, rvol: v.rvol })
    }
    if (tkDn && ip.belowCloud) {
      signals.push({ time: c.time, kind: 'tk_short', price: c.close, rvol: v.rvol })
    }
    if (
      ip.cloudTop != null &&
      prev.cloudTop != null &&
      pc.close <= prev.cloudTop &&
      c.close > ip.cloudTop
    ) {
      signals.push({ time: c.time, kind: 'brk_long', price: c.close, rvol: v.rvol })
    }
    if (
      ip.cloudBot != null &&
      prev.cloudBot != null &&
      pc.close >= prev.cloudBot &&
      c.close < ip.cloudBot
    ) {
      signals.push({ time: c.time, kind: 'brk_short', price: c.close, rvol: v.rvol })
    }
  }

  return { volumes, signals }
}

export function biasFromIchi(above: boolean, below: boolean): 'bull' | 'bear' | 'neutral' {
  if (above) return 'bull'
  if (below) return 'bear'
  return 'neutral'
}

export function signalLabel(kind: SignalKind): string {
  switch (kind) {
    case 'tk_long':
      return 'TK↑ + VOL'
    case 'tk_short':
      return 'TK↓ + VOL'
    case 'brk_long':
      return 'Cloud↑ + VOL'
    case 'brk_short':
      return 'Cloud↓ + VOL'
    default: {
      const _e: never = kind
      return _e
    }
  }
}
