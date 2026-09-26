/**
 * IntelligenceChart — bougies OHLCV + Ichimoku + volume (lightweight-charts,
 * bibliothèque déjà utilisée par PriceChart) et une surface React pour les
 * couches de dessin (children → DrawingLayer).
 *
 * Isolé de PriceChart : PriceChart va chercher ses overlays au moteur et dessine
 * les ChartObjects en price lines pleine largeur ; ici on reçoit tout en props
 * (réponse Chart Intelligence) et les dessins sont des composants React
 * sélectionnables. Mêmes tokens (readChartColors), même thème, même locale.
 */

import { useEffect, useRef, useState, type ReactNode } from 'react'
import {
  AreaSeries,
  CandlestickSeries,
  ColorType,
  createChart,
  HistogramSeries,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type Logical,
  type UTCTimestamp,
} from 'lightweight-charts'
import type { IntelligenceIchimokuPoint } from '../../lib/chartIntelligence'
import { type ChartColors, readChartColors, withAlpha } from '../../lib/chartColors'
import type { ProjectedKumoPoint } from '../../lib/engineIndicators'
import { THEME_CHANGE_EVENT } from '../../lib/theme'
import type { ChartCamera } from '../../lib/chartIntelligenceBriefing'
import type { Candle } from '../../lib/types'
import { ChartProjectionContext, type ChartProjection } from './chartProjection'

interface Props {
  candles: Candle[]
  ichimoku?: IntelligenceIchimokuPoint[]
  projection?: ProjectedKumoPoint[]
  showIchimoku?: boolean
  showVolume?: boolean
  /** Changer cette clé (symbole / timeframe) recadre le graphique. */
  resetKey?: string
  /**
   * Caméra briefing : follow N barres / fit tout / manual (ne pas forcer).
   * `token` force un re-cadrage (changement de période).
   */
  camera?: ChartCamera | null
  /** Clic sur le fond du graphique (hors dessin) — ex. désélection. */
  onBackgroundClick?: () => void
  /** Couches React (DrawingLayer…). */
  children?: ReactNode
  height?: number
  /** Durée d’une barre (s) du timeframe courant (ex. 3600 pour 1h). */
  barSeconds?: number
}

type SeriesBag = {
  candle: ISeriesApi<'Candlestick'>
  tenkan: ISeriesApi<'Line'>
  kijun: ISeriesApi<'Line'>
  spanA: ISeriesApi<'Line'>
  spanB: ISeriesApi<'Line'>
  cloudUpper: ISeriesApi<'Area'>
  cloudLower: ISeriesApi<'Area'>
  volume: ISeriesApi<'Histogram'>
}

const ts = (t: number) => t as UTCTimestamp

/** Axe des prix fr-FR (identique PriceChart). */
function fmtAxisPrice(n: number): string {
  if (!Number.isFinite(n)) return ''
  const a = Math.abs(n)
  const digits = a >= 10_000 ? 0 : a >= 100 ? 1 : a >= 1 ? 2 : 4
  return n.toLocaleString('fr-FR', { minimumFractionDigits: 0, maximumFractionDigits: digits })
}

function applyTheme(chart: IChartApi, s: SeriesBag, colors: ChartColors) {
  const grid = withAlpha(colors.grid || colors.border, 0.55)
  const cloudFill = withAlpha(colors.cloud, 0.45)
  chart.applyOptions({
    layout: {
      background: { type: ColorType.Solid, color: colors.background },
      textColor: colors.muted,
      fontFamily: 'var(--font-sans), system-ui, sans-serif',
    },
    grid: { vertLines: { color: grid }, horzLines: { color: grid } },
    crosshair: {
      mode: 1,
      vertLine: { color: withAlpha(colors.muted, 0.35), labelBackgroundColor: colors.background },
      horzLine: { color: withAlpha(colors.muted, 0.35), labelBackgroundColor: colors.background },
    },
  })
  s.candle.applyOptions({
    upColor: colors.bull,
    downColor: colors.bear,
    borderUpColor: colors.bull,
    borderDownColor: colors.bear,
    wickUpColor: colors.bull,
    wickDownColor: colors.bear,
  })
  s.tenkan.applyOptions({ color: colors.tenkan, lineWidth: 1 })
  s.kijun.applyOptions({ color: colors.kijun, lineWidth: 1 })
  s.spanA.applyOptions({ color: withAlpha(colors.spanA, 0.7), lineWidth: 1 })
  s.spanB.applyOptions({ color: withAlpha(colors.spanB, 0.7), lineWidth: 1 })
  s.cloudUpper.applyOptions({ topColor: cloudFill, bottomColor: cloudFill })
  s.cloudLower.applyOptions({ topColor: colors.background, bottomColor: colors.background })
}

function applyCamera(
  chart: IChartApi,
  nBars: number,
  camera: ChartCamera | null | undefined,
  candles?: { time: number }[],
) {
  if (!camera || camera.mode === 'manual' || nBars <= 0) return
  const scale = chart.timeScale()
  if (camera.fromTime != null && candles?.length) {
    let fromIdx = 0
    for (let i = 0; i < candles.length; i++) {
      if (candles[i]!.time >= camera.fromTime) {
        fromIdx = i
        break
      }
      fromIdx = i
    }
    const to = nBars - 1 + 2
    scale.setVisibleLogicalRange({ from: Math.max(-2, fromIdx - 1), to })
    return
  }
  if (camera.mode === 'fit' || camera.visibleBars == null) {
    scale.fitContent()
    return
  }
  const span = Math.max(8, Math.min(camera.visibleBars, nBars))
  const to = nBars - 1 + 2
  const from = Math.max(-2, to - span)
  scale.setVisibleLogicalRange({ from, to })
}

/**
 * Largeur de la zone de tracé (hors échelle de prix droite).
 * Repli hôte uniquement si `scaleWidth === 0` (1er paint dialog).
 */
export function plotWidthPx(
  scaleWidth: number,
  hostClientWidth: number,
  rightPriceScaleWidth: number,
): number {
  if (scaleWidth > 0) return scaleWidth
  return Math.max(0, hostClientWidth - Math.max(0, rightPriceScaleWidth))
}

export function IntelligenceChart({
  candles,
  ichimoku = [],
  projection = [],
  showIchimoku = true,
  showVolume = true,
  resetKey,
  camera = null,
  onBackgroundClick,
  children,
  height = 460,
  barSeconds,
}: Props) {
  const hostRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<SeriesBag | null>(null)
  const colorsRef = useRef<ChartColors | null>(null)
  const originRef = useRef<{ t0: number; bar: number }>({
    t0: 0,
    bar: barSeconds && barSeconds > 0 ? barSeconds : 3600,
  })
  const barSecondsRef = useRef(barSeconds)
  const fittedKeyRef = useRef<string | null>(null)
  const cameraTokenRef = useRef<number | null>(null)
  const rafRef = useRef<number | null>(null)
  const onBgRef = useRef(onBackgroundClick)
  const [projectionCtx, setProjectionCtx] = useState<ChartProjection | null>(null)

  useEffect(() => {
    barSecondsRef.current = barSeconds
    if (barSeconds && barSeconds > 0) {
      originRef.current = { ...originRef.current, bar: barSeconds }
    }
  }, [barSeconds])

  useEffect(() => {
    onBgRef.current = onBackgroundClick
  }, [onBackgroundClick])

  /**
   * Recalcule la projection au prochain frame (pan, zoom, autoscale, resize) :
   * nouvel objet → re-rendu des couches React.
   */
  const bump = () => {
    if (rafRef.current != null) return
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = null
      const chart = chartRef.current
      const series = seriesRef.current
      const host = hostRef.current
      if (!chart || !series) return
      const scale = chart.timeScale()
      const toX = (logical: number) => {
        const c = scale.logicalToCoordinate(logical as Logical)
        return c == null ? null : Number(c)
      }
      // CI-T1 : repli hôte − échelle droite seulement si timeScale.width() === 0
      const rightW = chart.priceScale('right').width()
      const width = plotWidthPx(scale.width() || 0, host?.clientWidth || 0, rightW)
      const heightPx = Math.max(
        chart.paneSize(0)?.height || 0,
        host?.clientHeight || 0,
      )
      if (!(width > 0) || !(heightPx > 0)) return
      setProjectionCtx((prev) => ({
        x: (time: number) => {
          const { t0, bar } = originRef.current
          const step = bar > 0 ? bar : barSecondsRef.current && barSecondsRef.current > 0 ? barSecondsRef.current : 3600
          return toX((time - t0) / step)
        },
        y: (price: number) => {
          const c = series.candle.priceToCoordinate(price)
          return c == null ? null : Number(c)
        },
        width,
        height: heightPx,
        barSpacing: Math.abs((toX(1) ?? 0) - (toX(0) ?? 0)) || 6,
        rev: (prev?.rev ?? 0) + 1,
      }))
    })
  }

  useEffect(() => {
    const el = hostRef.current
    if (!el) return
    const colors = readChartColors()
    colorsRef.current = colors
    const chart = createChart(el, {
      width: el.clientWidth || 800,
      height: el.clientHeight || height,
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false, rightOffset: 6 },
      localization: { locale: 'fr-FR', priceFormatter: fmtAxisPrice },
    })
    const quiet = { lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false } as const
    const area = { ...quiet, lineWidth: 1 as const, lineColor: 'transparent' }
    const cloudUpper = chart.addSeries(AreaSeries, { ...area, topColor: 'transparent', bottomColor: 'transparent' }, 0)
    const cloudLower = chart.addSeries(AreaSeries, { ...area, topColor: 'transparent', bottomColor: 'transparent' }, 0)
    const candle = chart.addSeries(CandlestickSeries, { ...quiet, lastValueVisible: true }, 0)
    const tenkan = chart.addSeries(LineSeries, { lineWidth: 1, ...quiet }, 0)
    const kijun = chart.addSeries(LineSeries, { lineWidth: 1, ...quiet }, 0)
    const spanA = chart.addSeries(LineSeries, { lineWidth: 1, ...quiet }, 0)
    const spanB = chart.addSeries(LineSeries, { lineWidth: 1, ...quiet }, 0)
    const volume = chart.addSeries(
      HistogramSeries,
      { priceFormat: { type: 'volume' }, priceScaleId: 'volume', ...quiet },
      0,
    )
    chart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 }, borderVisible: false })
    const bag: SeriesBag = { candle, tenkan, kijun, spanA, spanB, cloudUpper, cloudLower, volume }
    applyTheme(chart, bag, colors)
    chartRef.current = chart
    seriesRef.current = bag

    const ro = new ResizeObserver(() => {
      if (!hostRef.current) return
      chart.applyOptions({ width: hostRef.current.clientWidth, height: hostRef.current.clientHeight })
      bump()
    })
    ro.observe(el)
    chart.timeScale().subscribeVisibleLogicalRangeChange(bump)
    const onClick = () => onBgRef.current?.()
    chart.subscribeClick(onClick)
    // Le drag de l'échelle de prix n'émet pas d'événement : on suit le pointeur.
    const onPointer = () => bump()
    el.addEventListener('pointermove', onPointer)
    el.addEventListener('wheel', onPointer, { passive: true })
    const onTheme = () => {
      const next = readChartColors()
      colorsRef.current = next
      applyTheme(chart, bag, next)
      bump()
    }
    window.addEventListener(THEME_CHANGE_EVENT, onTheme)

    return () => {
      window.removeEventListener(THEME_CHANGE_EVENT, onTheme)
      el.removeEventListener('pointermove', onPointer)
      el.removeEventListener('wheel', onPointer)
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(bump)
      chart.unsubscribeClick(onClick)
      ro.disconnect()
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current)
      chart.remove()
      chartRef.current = null
      seriesRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Données : bougies + volume + Ichimoku (fournis par la source, aucun calcul ici).
  useEffect(() => {
    const chart = chartRef.current
    const s = seriesRef.current
    const colors = colorsRef.current
    if (!chart || !s || !colors) return
    if (candles.length >= 1) {
      const fromSeries =
        candles.length >= 2 ? candles[1]!.time - candles[0]!.time : 0
      const fromTf = barSecondsRef.current && barSecondsRef.current > 0 ? barSecondsRef.current : 0
      originRef.current = {
        t0: candles[0]!.time,
        bar: fromSeries > 0 ? fromSeries : fromTf > 0 ? fromTf : originRef.current.bar,
      }
    }
    s.candle.setData(
      candles.map((c) => ({ time: ts(c.time), open: c.open, high: c.high, low: c.low, close: c.close })),
    )
    s.volume.setData(
      candles.map((c) => ({
        time: ts(c.time),
        value: c.volume,
        color: withAlpha(c.close >= c.open ? colors.bull : colors.bear, 0.28),
      })),
    )
    const line = (key: 'tenkan' | 'kijun') =>
      ichimoku
        .filter((p) => p[key] != null)
        .map((p) => ({ time: ts(p.time), value: p[key] as number }))
    s.tenkan.setData(line('tenkan'))
    s.kijun.setData(line('kijun'))
    s.spanA.setData(projection.map((p) => ({ time: ts(p.time), value: p.senkouA })))
    s.spanB.setData(projection.map((p) => ({ time: ts(p.time), value: p.senkouB })))
    s.cloudUpper.setData(projection.map((p) => ({ time: ts(p.time), value: Math.max(p.senkouA, p.senkouB) })))
    s.cloudLower.setData(projection.map((p) => ({ time: ts(p.time), value: Math.min(p.senkouA, p.senkouB) })))

    const key = resetKey ?? 'default'
    const camToken = camera?.token ?? -1
    const needFit =
      candles.length > 0 &&
      (fittedKeyRef.current !== key || cameraTokenRef.current !== camToken)
    if (needFit) {
      applyCamera(chart, candles.length, camera, candles)
      fittedKeyRef.current = key
      cameraTokenRef.current = camToken
    } else if (camera?.mode === 'follow' && candles.length > 0) {
      // Replay progressif : coller la fenêtre à droite quand le slice avance.
      applyCamera(chart, candles.length, camera, candles)
    }
    // Autoscale appliqué au frame suivant → deux frames avant de reprojeter.
    requestAnimationFrame(() => bump())
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candles, ichimoku, projection, resetKey, camera?.token, camera?.mode, camera?.visibleBars, camera?.fromTime])

  useEffect(() => {
    const s = seriesRef.current
    if (!s) return
    for (const k of ['tenkan', 'kijun', 'spanA', 'spanB', 'cloudUpper', 'cloudLower'] as const) {
      s[k].applyOptions({ visible: showIchimoku })
    }
    s.volume.applyOptions({ visible: showVolume })
    bump()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showIchimoku, showVolume])

  return (
    <div className="ci-chart" style={{ height }}>
      <div className="ci-chart-host" ref={hostRef} />
      <ChartProjectionContext.Provider value={projectionCtx}>
        <div className="ci-chart-overlay" style={{ width: projectionCtx?.width || undefined }}>
          {projectionCtx && projectionCtx.width > 0 && projectionCtx.height > 0 ? children : null}
        </div>
      </ChartProjectionContext.Provider>
    </div>
  )
}
