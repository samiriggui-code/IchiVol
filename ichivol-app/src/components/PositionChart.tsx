import { useEffect, useRef } from 'react'
import {
  CandlestickSeries,
  ColorType,
  createChart,
  LineStyle,
  type UTCTimestamp,
} from 'lightweight-charts'

interface Candle {
  time: number
  open: number
  high: number
  low: number
  close: number
}

/** Mini graphique d'un trade : bougies + lignes entrée / stop / objectif. Autonome. */
export function PositionChart({
  candles,
  entry,
  stop,
  target,
  exit,
}: {
  candles: Candle[]
  entry: number
  stop?: number | null
  target?: number | null
  exit?: number | null
}) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el || candles.length === 0) return
    const css = getComputedStyle(document.documentElement)
    const bull = css.getPropertyValue('--bull').trim() || '#16a34a'
    const bear = css.getPropertyValue('--bear').trim() || '#dc2626'
    const muted = css.getPropertyValue('--muted').trim() || '#888'
    const chart = createChart(el, {
      height: 260,
      layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: muted },
      grid: { vertLines: { visible: false }, horzLines: { color: 'rgba(128,128,128,0.15)' } },
      timeScale: { timeVisible: true, borderVisible: false },
      rightPriceScale: { borderVisible: false },
    })
    const series = chart.addSeries(CandlestickSeries, {
      upColor: bull,
      downColor: bear,
      wickUpColor: bull,
      wickDownColor: bear,
      borderVisible: false,
    })
    series.setData(
      candles.map((c) => ({
        time: c.time as UTCTimestamp,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })),
    )
    const line = (p: number | null | undefined, color: string, title: string) => {
      if (p == null || !Number.isFinite(p)) return
      series.createPriceLine({
        price: p,
        color,
        lineStyle: LineStyle.Dashed,
        lineWidth: 1,
        axisLabelVisible: true,
        title,
      })
    }
    line(entry, muted, 'Entrée')
    line(stop, bear, 'Stop')
    line(target, bull, 'Objectif')
    line(exit, muted, 'Sortie')
    chart.timeScale().fitContent()
    const onResize = () => chart.applyOptions({ width: el.clientWidth })
    onResize()
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      chart.remove()
    }
  }, [candles, entry, stop, target, exit])

  if (candles.length === 0) return <p className="muted">Graphique indisponible.</p>
  return <div ref={ref} className="position-chart" />
}
