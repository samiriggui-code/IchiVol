import { readChartColors } from './chartColors'
import type { EngineRvolState } from './engineIndicators'
import {
  type Candle,
  type IchimokuPoint,
  type Signal,
  type SignalKind,
  type VolumePoint,
} from './types'

/**
 * Couleurs volume + marqueurs de signaux à partir des séries moteur
 * (plus de recalcul Ichimoku / RVOL ici).
 */
export function buildVolumePulse(
  candles: Candle[],
  ichi: IchimokuPoint[],
  rvolSeries: EngineRvolState[],
): { volumes: VolumePoint[]; signals: Signal[] } {
  const colors = readChartColors()
  const ichiByTime = new Map(ichi.map((p) => [p.time, p]))
  const rvolByTime = new Map(rvolSeries.map((r) => [r.time, r]))

  const volumes: VolumePoint[] = []
  for (const c of candles) {
    const ip = ichiByTime.get(c.time)
    const rv = rvolByTime.get(c.time)
    const rvol = rv?.rvol ?? 0
    const confirmed = rv?.confirmed ?? false
    const spike = rv?.spike ?? false
    const volAvg = rv?.avg_volume ?? 0

    let color: string = colors.weak
    if (ip && c.volume >= volAvg) {
      if (ip.aboveCloud) color = spike ? colors.bull : `${colors.bull}99`
      else if (ip.belowCloud) color = spike ? colors.bear : `${colors.bear}99`
      else color = spike ? colors.neutral : `${colors.neutral}99`
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

  const signals: Signal[] = []
  for (let i = 1; i < candles.length; i++) {
    const v = volumes[i]
    if (!v.confirmed) continue
    const c = candles[i]
    const pc = candles[i - 1]
    const ip = ichiByTime.get(c.time)
    const prev = ichiByTime.get(pc.time)
    if (!ip || !prev) continue

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
