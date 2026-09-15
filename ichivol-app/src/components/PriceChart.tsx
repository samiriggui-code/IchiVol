import { useEffect, useRef } from 'react'
import {
  CandlestickSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  HistogramSeries,
  LineSeries,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type SeriesMarker,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts'
import { computeIchimoku, projectedSpans } from '../lib/ichimoku'
import { computeVolumePulse } from '../lib/signals'
import {
  COLORS,
  DEFAULT_ICHI,
  DEFAULT_VOL,
  type Candle,
  type Signal,
} from '../lib/types'

interface Props {
  candles: Candle[]
  onSignals?: (signals: Signal[]) => void
}

type SeriesBag = {
  candle: ISeriesApi<'Candlestick'>
  tenkan: ISeriesApi<'Line'>
  kijun: ISeriesApi<'Line'>
  spanA: ISeriesApi<'Line'>
  spanB: ISeriesApi<'Line'>
  volume: ISeriesApi<'Histogram'>
}

function ts(t: number): UTCTimestamp {
  return t as UTCTimestamp
}

function asLine(
  rows: { time: number; value: number | null }[],
): { time: UTCTimestamp; value: number }[] {
  return rows
    .filter((r): r is { time: number; value: number } => r.value != null)
    .map((r) => ({ time: ts(r.time), value: r.value }))
}

export function PriceChart({ candles, onSignals }: Props) {
  const hostRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<SeriesBag | null>(null)
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null)

  useEffect(() => {
    const el = hostRef.current
    if (!el) return

    const chart = createChart(el, {
      width: el.clientWidth || 800,
      height: el.clientHeight || 480,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: COLORS.muted,
        fontFamily: "'IBM Plex Sans', system-ui, sans-serif",
      },
      grid: {
        vertLines: { color: 'rgba(30,42,48,0.65)' },
        horzLines: { color: 'rgba(30,42,48,0.65)' },
      },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false },
      crosshair: {
        vertLine: { color: 'rgba(138,160,168,0.35)' },
        horzLine: { color: 'rgba(138,160,168,0.35)' },
      },
    })

    const ro = new ResizeObserver(() => {
      if (!hostRef.current) return
      chart.applyOptions({
        width: hostRef.current.clientWidth,
        height: hostRef.current.clientHeight,
      })
    })
    ro.observe(el)

    const candle = chart.addSeries(
      CandlestickSeries,
      {
        upColor: COLORS.bull,
        downColor: COLORS.bear,
        borderUpColor: COLORS.bull,
        borderDownColor: COLORS.bear,
        wickUpColor: COLORS.bull,
        wickDownColor: COLORS.bear,
      },
      0,
    )
    const tenkan = chart.addSeries(
      LineSeries,
      { color: COLORS.tenkan, lineWidth: 2, title: 'Tenkan' },
      0,
    )
    const kijun = chart.addSeries(
      LineSeries,
      { color: COLORS.kijun, lineWidth: 2, title: 'Kijun' },
      0,
    )
    const spanA = chart.addSeries(
      LineSeries,
      { color: COLORS.spanA, lineWidth: 1, lineStyle: LineStyle.Dashed, title: 'Span A' },
      0,
    )
    const spanB = chart.addSeries(
      LineSeries,
      { color: COLORS.spanB, lineWidth: 1, lineStyle: LineStyle.Dashed, title: 'Span B' },
      0,
    )
    const volume = chart.addSeries(
      HistogramSeries,
      { priceFormat: { type: 'volume' }, priceScaleId: '' },
      1,
    )
    volume.priceScale().applyOptions({ scaleMargins: { top: 0.2, bottom: 0 } })
    const panes = chart.panes()
    if (panes[1]) panes[1].setHeight(110)

    markersRef.current = createSeriesMarkers(candle, [])
    chartRef.current = chart
    seriesRef.current = { candle, tenkan, kijun, spanA, spanB, volume }

    return () => {
      ro.disconnect()
      chart.remove()
      chartRef.current = null
      seriesRef.current = null
      markersRef.current = null
    }
  }, [])

  useEffect(() => {
    const chart = chartRef.current
    const series = seriesRef.current
    if (!chart || !series || candles.length === 0) return

    const ichi = computeIchimoku(candles, DEFAULT_ICHI)
    const proj = projectedSpans(candles, DEFAULT_ICHI)
    const { volumes, signals } = computeVolumePulse(candles, DEFAULT_ICHI, DEFAULT_VOL)
    onSignals?.(signals)

    series.candle.setData(
      candles.map((c) => ({
        time: ts(c.time),
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })),
    )
    series.tenkan.setData(asLine(ichi.map((p) => ({ time: p.time, value: p.tenkan }))))
    series.kijun.setData(asLine(ichi.map((p) => ({ time: p.time, value: p.kijun }))))
    series.spanA.setData(asLine(proj.map((p) => ({ time: p.time, value: p.senkouA }))))
    series.spanB.setData(asLine(proj.map((p) => ({ time: p.time, value: p.senkouB }))))
    series.volume.setData(
      volumes.map((v) => ({ time: ts(v.time), value: v.volume, color: v.color })),
    )

    const markers: SeriesMarker<Time>[] = signals.map((s) => {
      const isLong = s.kind === 'tk_long' || s.kind === 'brk_long'
      return {
        time: ts(s.time),
        position: isLong ? 'belowBar' : 'aboveBar',
        color: isLong ? COLORS.bull : COLORS.bear,
        shape: isLong ? 'arrowUp' : 'arrowDown',
        text: isLong ? 'VOL↑' : 'VOL↓',
      }
    })
    markersRef.current?.setMarkers(markers)
    chart.timeScale().fitContent()
  }, [candles, onSignals])

  return <div className="chart-host" ref={hostRef} />
}
