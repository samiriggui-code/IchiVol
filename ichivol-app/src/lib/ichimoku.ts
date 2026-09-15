import type { Candle, IchimokuParams, IchimokuPoint } from './types'

function donchianMid(candles: Candle[], end: number, len: number): number | null {
  if (end - len + 1 < 0) return null
  let hi = -Infinity
  let lo = Infinity
  for (let i = end - len + 1; i <= end; i++) {
    hi = Math.max(hi, candles[i].high)
    lo = Math.min(lo, candles[i].low)
  }
  return (hi + lo) / 2
}

export function computeIchimoku(
  candles: Candle[],
  params: IchimokuParams,
): IchimokuPoint[] {
  const { tenkan: tLen, kijun: kLen, senkouB: bLen, displacement: d } = params
  const n = candles.length
  const tenkanArr: (number | null)[] = Array(n).fill(null)
  const kijunArr: (number | null)[] = Array(n).fill(null)
  const spanARaw: (number | null)[] = Array(n).fill(null)
  const spanBRaw: (number | null)[] = Array(n).fill(null)

  for (let i = 0; i < n; i++) {
    const tenkan = donchianMid(candles, i, tLen)
    const kijun = donchianMid(candles, i, kLen)
    tenkanArr[i] = tenkan
    kijunArr[i] = kijun
    if (tenkan != null && kijun != null) spanARaw[i] = (tenkan + kijun) / 2
    spanBRaw[i] = donchianMid(candles, i, bLen)
  }

  const out: IchimokuPoint[] = []
  for (let i = 0; i < n; i++) {
    const cloudIdx = i - d
    const sa = cloudIdx >= 0 ? spanARaw[cloudIdx] : null
    const sb = cloudIdx >= 0 ? spanBRaw[cloudIdx] : null
    let cloudTop: number | null = null
    let cloudBot: number | null = null
    let cloudBullish = false
    if (sa != null && sb != null) {
      cloudTop = Math.max(sa, sb)
      cloudBot = Math.min(sa, sb)
      cloudBullish = sa >= sb
    }
    const close = candles[i].close
    const chikouIdx = i + d
    out.push({
      time: candles[i].time,
      tenkan: tenkanArr[i],
      kijun: kijunArr[i],
      senkouA: i >= d ? spanARaw[i - d] : null,
      senkouB: i >= d ? spanBRaw[i - d] : null,
      chikou: chikouIdx < n ? candles[chikouIdx].close : null,
      cloudTop,
      cloudBot,
      aboveCloud: cloudTop != null && close > cloudTop,
      belowCloud: cloudBot != null && close < cloudBot,
      cloudBullish,
    })
  }
  return out
}

export function projectedSpans(
  candles: Candle[],
  params: IchimokuParams,
): { time: number; senkouA: number; senkouB: number }[] {
  const d = params.displacement
  const n = candles.length
  const lastTime = candles[n - 1]?.time ?? 0
  const step = n >= 2 ? candles[n - 1].time - candles[n - 2].time : 3600
  const out: { time: number; senkouA: number; senkouB: number }[] = []
  for (let i = 0; i < n; i++) {
    const tenkan = donchianMid(candles, i, params.tenkan)
    const kijun = donchianMid(candles, i, params.kijun)
    const sa = tenkan != null && kijun != null ? (tenkan + kijun) / 2 : null
    const sb = donchianMid(candles, i, params.senkouB)
    if (sa == null || sb == null) continue
    const t = i + d < n ? candles[i + d].time : lastTime + (i + d - n + 1) * step
    out.push({ time: t, senkouA: sa, senkouB: sb })
  }
  return out
}
