import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import {
  AreaSeries,
  CandlestickSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  HistogramSeries,
  LineSeries,
  LineStyle,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type MouseEventParams,
  type SeriesMarker,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts'
import {
  DEFAULT_LAYERS,
  OBJECT_LAYER_KEYS,
  layerFromSource,
  type LayerPrefs,
} from '../lib/marketPrefs'
import {
  chartObjectMarkers,
  chartObjectPriceLevels,
  chartObjectTrendlines,
  chartObjectZones,
  type ChartObject,
} from '../lib/chartObjects'
import { type ChartColors, readChartColors, withAlpha } from '../lib/chartColors'
import { fetchChartOverlays } from '../lib/engineIndicators'
import { getSettings } from '../lib/settings'
import { biasFromIchi, buildVolumePulse, signalLabel } from '../lib/signals'
import { THEME_CHANGE_EVENT } from '../lib/theme'
import {
  DEFAULT_ICHI,
  DEFAULT_VOL,
  type Candle,
  type IchimokuPoint,
  type Interval,
  type Signal,
  type VolumePoint,
} from '../lib/types'

export type ChartPickPoint = { time: number; price: number }

interface Props {
  candles: Candle[]
  symbol: string
  timeframe: Interval | string
  onSignals?: (signals: Signal[]) => void
  onLive?: (live: { bias: 'bull' | 'bear' | 'neutral'; rvol: number }) => void
  /** ChartObjects moteur (zones / trendlines / markers) — filtered by layer prefs. */
  chartObjects?: ChartObject[] | null
  /** T2c: when true, chart clicks emit onPickPoint (mark-trade mode). */
  pickMode?: boolean
  onPickPoint?: (point: ChartPickPoint) => void
  /** Global layer visibility (persisted by Market page). */
  layerPrefs?: LayerPrefs
  onLayerPrefsChange?: (next: LayerPrefs) => void
  /** Volume pane height in px (persisted). */
  volumeHeight?: number
  onVolumeHeightChange?: (h: number) => void
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

type HoverPoint = {
  time: number
  candle: Candle
  ichi: IchimokuPoint
  volume: VolumePoint
  signal: Signal | null
  bias: 'bull' | 'bear' | 'neutral'
}

type TipState = {
  visible: boolean
  x: number
  y: number
  point: HoverPoint | null
}

type LayerKey =
  | 'candles'
  | 'tenkan'
  | 'kijun'
  | 'spanA'
  | 'spanB'
  | 'volume'
  | 'signals'
  | 'structure'

type LayerVis = Record<LayerKey, boolean>

const LOCAL_DEFAULT: LayerVis = {
  candles: true,
  tenkan: true,
  kijun: true,
  spanA: true,
  spanB: true,
  volume: true,
  signals: false,
  structure: false,
}

function filterObjectsByLayers(
  objects: ChartObject[] | null | undefined,
  prefs: LayerPrefs,
): ChartObject[] {
  if (!objects?.length) return []
  return objects.filter((o) => {
    const layer = layerFromSource(o.source, o.layer)
    return prefs[layer] !== false
  })
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

function fmtPrice(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return '—'
  return n.toLocaleString(undefined, { maximumFractionDigits: 6 })
}

/** Axe des prix fr-FR : « 90 000 », « 2 718,5 », « 0,5862 » (maquette). */
function fmtAxisPrice(n: number): string {
  if (!Number.isFinite(n)) return ''
  const a = Math.abs(n)
  const digits = a >= 10_000 ? 0 : a >= 100 ? 1 : a >= 1 ? 2 : 4
  return n.toLocaleString('fr-FR', { minimumFractionDigits: 0, maximumFractionDigits: digits })
}

function fmtVol(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return n.toFixed(0)
}

function timeToUnix(time: Time): number | null {
  if (typeof time === 'number') return time
  if (typeof time === 'string') {
    const parsed = Date.parse(time)
    return Number.isNaN(parsed) ? null : Math.floor(parsed / 1000)
  }
  if (time && typeof time === 'object' && 'year' in time) {
    return Math.floor(Date.UTC(time.year, time.month - 1, time.day) / 1000)
  }
  return null
}

function applyChartTheme(chart: IChartApi, series: SeriesBag, colors: ChartColors) {
  const grid = withAlpha(colors.grid || colors.border, 0.55)
  const cloudFill = withAlpha(colors.cloud, 0.45)
  chart.applyOptions({
    layout: {
      background: { type: ColorType.Solid, color: colors.background },
      textColor: colors.muted,
      fontFamily: "var(--font-sans), system-ui, sans-serif",
    },
    grid: {
      vertLines: { color: grid },
      horzLines: { color: grid },
    },
    crosshair: {
      mode: 1,
      vertLine: { color: withAlpha(colors.muted, 0.35), labelBackgroundColor: colors.background },
      horzLine: { color: withAlpha(colors.muted, 0.35), labelBackgroundColor: colors.background },
    },
  })
  series.candle.applyOptions({
    upColor: colors.bull,
    downColor: colors.bear,
    borderUpColor: colors.bull,
    borderDownColor: colors.bear,
    wickUpColor: colors.bull,
    wickDownColor: colors.bear,
  })
  series.tenkan.applyOptions({ color: colors.tenkan, lineWidth: 1 })
  series.kijun.applyOptions({ color: colors.kijun, lineWidth: 1 })
  series.spanA.applyOptions({ color: withAlpha(colors.spanA, 0.7), lineWidth: 1 })
  series.spanB.applyOptions({ color: withAlpha(colors.spanB, 0.7), lineWidth: 1 })
  series.cloudUpper.applyOptions({
    lineColor: 'transparent',
    topColor: cloudFill,
    bottomColor: cloudFill,
    priceLineVisible: false,
    lastValueVisible: false,
    crosshairMarkerVisible: false,
  })
  series.cloudLower.applyOptions({
    lineColor: 'transparent',
    topColor: colors.background,
    bottomColor: colors.background,
    priceLineVisible: false,
    lastValueVisible: false,
    crosshairMarkerVisible: false,
  })
}

/** Volume bar color from candle direction at ~0.28 opacity (maquette). */
function volumeBarColor(open: number, close: number, colors: ChartColors): string {
  const up = close >= open
  return withAlpha(up ? colors.bull : colors.bear, 0.28)
}

/** Render ChartObjects (ENGINE + USER/CLAUDE) with Structure visual parity + T2b levels. */
function renderChartObjects(
  chart: IChartApi | null,
  series: SeriesBag | null,
  priceLinesRef: { current: IPriceLine[] },
  trendSeriesRef: { current: ISeriesApi<'Line'>[] },
  objects: ChartObject[] | null | undefined,
  show: boolean,
  colors: ChartColors,
): SeriesMarker<Time>[] {
  if (!chart || !series) return []

  for (const pl of priceLinesRef.current) series.candle.removePriceLine(pl)
  priceLinesRef.current = []
  for (const ts_ of trendSeriesRef.current) chart.removeSeries(ts_)
  trendSeriesRef.current = []

  if (!objects || !show) return []

  for (const z of chartObjectZones(objects)) {
    const color = z.side === 'support' ? colors.bull : colors.bear
    const alpha = z.faded ? '55' : 'b3'
    const label =
      z.label ||
      (z.touch_count
        ? `${z.side === 'support' ? 'S' : 'R'} ×${z.touch_count}`
        : z.side === 'support'
          ? 'S'
          : 'R')
    for (const [price, title] of [[z.high, label], [z.low, '']] as const) {
      priceLinesRef.current.push(
        series.candle.createPriceLine({
          price,
          color: `${color}${alpha}`,
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: Boolean(title),
          title: title ? (z.side === 'support' ? 'S' : 'R') : '',
        }),
      )
    }
  }

  for (const lvl of chartObjectPriceLevels(objects)) {
    let color = colors.muted
    if (lvl.kind === 'entry') color = colors.bull
    else if (lvl.kind === 'stop') color = colors.bear
    else if (lvl.kind === 'target') color = colors.bull
    priceLinesRef.current.push(
      series.candle.createPriceLine({
        price: lvl.price,
        color: `${color}cc`,
        lineWidth: lvl.kind === 'horizontal_line' ? 1 : 2,
        lineStyle:
          lvl.kind === 'stop' || lvl.subtype === 'sr_nearest' ? LineStyle.Dashed : LineStyle.Solid,
        axisLabelVisible: true,
        title: lvl.label,
      }),
    )
  }

  for (const t of chartObjectTrendlines(objects)) {
    const color = t.side === 'support' ? colors.bull : colors.bear
    const line = chart.addSeries(
      LineSeries,
      {
        color,
        lineWidth: 1,
        lineStyle: t.ray ? LineStyle.Solid : LineStyle.Dashed,
        lastValueVisible: false,
        priceLineVisible: false,
        crosshairMarkerVisible: false,
      },
      0,
    )
    line.setData([
      { time: ts(t.start_time), value: t.start_price },
      { time: ts(t.end_time), value: t.end_price },
    ])
    trendSeriesRef.current.push(line)
  }

  return chartObjectMarkers(objects).map((m) => {
    const bullish = m.side === 'resistance' || m.side === 'LONG'
    let color = bullish ? colors.bull : colors.bear
    if (m.outcome === 'win') color = colors.bull
    else if (m.outcome === 'loss') color = colors.bear
    else if (m.outcome === 'flat') color = colors.muted
    return {
      time: ts(m.time),
      position: bullish ? ('belowBar' as const) : ('aboveBar' as const),
      color,
      shape: m.shape,
      text: m.label,
    }
  })
}

export function PriceChart({
  candles,
  symbol,
  timeframe,
  onSignals,
  onLive,
  chartObjects,
  pickMode = false,
  onPickPoint,
  layerPrefs,
  volumeHeight = 110,
  onVolumeHeightChange,
}: Props) {
  const priceLinesRef = useRef<IPriceLine[]>([])
  const trendSeriesRef = useRef<ISeriesApi<'Line'>[]>([])
  const structureMarkersRef = useRef<SeriesMarker<Time>[]>([])
  const hostRef = useRef<HTMLDivElement>(null)
  const wrapRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<SeriesBag | null>(null)
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null)
  const hoverMapRef = useRef<Map<number, HoverPoint>>(new Map())
  const signalsCacheRef = useRef<Signal[]>([])
  const volumeHeightRef = useRef(volumeHeight)
  const pickModeRef = useRef(pickMode)
  const onPickPointRef = useRef(onPickPoint)
  const [colors, setColors] = useState<ChartColors>(() => readChartColors())
  const [layers, setLayers] = useState<LayerVis>(() => ({
    ...LOCAL_DEFAULT,
    candles: layerPrefs?.candles ?? true,
    tenkan: layerPrefs?.tenkan ?? true,
    kijun: layerPrefs?.kijun ?? true,
    spanA: layerPrefs?.spanA ?? true,
    spanB: layerPrefs?.spanB ?? true,
    volume: layerPrefs?.volume ?? true,
    signals: layerPrefs?.signals ?? true,
    structure: layerPrefs?.structure ?? true,
  }))
  const layersRef = useRef<LayerVis>(layers)
  const [overlayError, setOverlayError] = useState<string | null>(null)
  const [overlaysReady, setOverlaysReady] = useState(false)
  const prefs: LayerPrefs = layerPrefs ?? { ...DEFAULT_LAYERS, ...layers }

  useEffect(() => {
    if (!layerPrefs) return
    setLayers({
      candles: layerPrefs.candles,
      tenkan: layerPrefs.tenkan,
      kijun: layerPrefs.kijun,
      spanA: layerPrefs.spanA,
      spanB: layerPrefs.spanB,
      volume: layerPrefs.volume,
      signals: layerPrefs.signals,
      structure: layerPrefs.structure,
    })
  }, [layerPrefs])

  useEffect(() => {
    layersRef.current = layers
  }, [layers])
  useEffect(() => {
    pickModeRef.current = pickMode
  }, [pickMode])
  useEffect(() => {
    onPickPointRef.current = onPickPoint
  }, [onPickPoint])
  useEffect(() => {
    volumeHeightRef.current = volumeHeight
    const series = seriesRef.current
    if (!series) return
    // Map persisted volumeHeight (40–280) → overlay top margin (~0.92–0.65)
    const clamped = Math.max(40, Math.min(280, volumeHeight))
    const top = 0.92 - ((clamped - 40) / 240) * 0.27
    series.volume.priceScale().applyOptions({ scaleMargins: { top, bottom: 0 } })
  }, [volumeHeight])

  const [tip, setTip] = useState<TipState>({
    visible: false,
    x: 0,
    y: 0,
    point: null,
  })

  useEffect(() => {
    const el = hostRef.current
    if (!el) return
    const initialColors = readChartColors()

    const chart = createChart(el, {
      width: el.clientWidth || 800,
      height: el.clientHeight || 480,
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false },
      localization: { locale: 'fr-FR', priceFormatter: fmtAxisPrice },
    })

    const ro = new ResizeObserver(() => {
      if (!hostRef.current) return
      chart.applyOptions({
        width: hostRef.current.clientWidth,
        height: hostRef.current.clientHeight,
      })
    })
    ro.observe(el)

    const seriesOpts = {
      lastValueVisible: false,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
    } as const
    const areaOpts = {
      lineWidth: 1 as const,
      lineColor: 'transparent',
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    }
    const cloudUpper = chart.addSeries(AreaSeries, { ...areaOpts, topColor: 'transparent', bottomColor: 'transparent' }, 0)
    const cloudLower = chart.addSeries(AreaSeries, { ...areaOpts, topColor: 'transparent', bottomColor: 'transparent' }, 0)
    const candle = chart.addSeries(CandlestickSeries, { ...seriesOpts }, 0)
    const tenkan = chart.addSeries(LineSeries, { lineWidth: 1, ...seriesOpts }, 0)
    const kijun = chart.addSeries(LineSeries, { lineWidth: 1, ...seriesOpts }, 0)
    const spanA = chart.addSeries(LineSeries, { lineWidth: 1, lineStyle: LineStyle.Solid, ...seriesOpts }, 0)
    const spanB = chart.addSeries(LineSeries, { lineWidth: 1, lineStyle: LineStyle.Solid, ...seriesOpts }, 0)
    // Volume overlay on price pane (maquette: bars at bottom, do not mask candles)
    const volume = chart.addSeries(
      HistogramSeries,
      { priceFormat: { type: 'volume' }, priceScaleId: 'volume', ...seriesOpts },
      0,
    )
    volume.priceScale().applyOptions({
      scaleMargins: { top: 0.78, bottom: 0 },
      borderVisible: false,
    })
    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.78, bottom: 0 },
      borderVisible: false,
    })

    const seriesBag: SeriesBag = { candle, tenkan, kijun, spanA, spanB, cloudUpper, cloudLower, volume }
    applyChartTheme(chart, seriesBag, initialColors)

    markersRef.current = createSeriesMarkers(candle, [])
    chartRef.current = chart
    seriesRef.current = seriesBag
    setColors(initialColors)

    const onMove = (param: MouseEventParams<Time>) => {
      if (pickModeRef.current) {
        setTip((prev) => (prev.visible ? { ...prev, visible: false, point: null } : prev))
        return
      }
      if (
        !param.point ||
        !param.time ||
        param.point.x < 0 ||
        param.point.y < 0 ||
        !wrapRef.current
      ) {
        setTip((prev) => (prev.visible ? { ...prev, visible: false, point: null } : prev))
        return
      }
      const unix = timeToUnix(param.time)
      if (unix == null) {
        setTip((prev) => (prev.visible ? { ...prev, visible: false, point: null } : prev))
        return
      }
      const point = hoverMapRef.current.get(unix) ?? null
      if (!point) {
        setTip((prev) => (prev.visible ? { ...prev, visible: false, point: null } : prev))
        return
      }

      const wrap = wrapRef.current
      const tipW = 240
      const tipH = 280
      let x = param.point.x + 16
      let y = param.point.y + 16
      if (x + tipW > wrap.clientWidth - 8) x = param.point.x - tipW - 12
      if (y + tipH > wrap.clientHeight - 8) y = Math.max(8, param.point.y - tipH - 8)
      x = Math.max(8, x)
      y = Math.max(8, y)

      setTip({ visible: true, x, y, point })
    }

    chart.subscribeCrosshairMove(onMove)

    const onClick = (param: MouseEventParams<Time>) => {
      if (!pickModeRef.current || !onPickPointRef.current) return
      if (!param.point || !param.time || !seriesRef.current) return
      const unix = timeToUnix(param.time)
      if (unix == null) return
      const price = seriesRef.current.candle.coordinateToPrice(param.point.y)
      if (price == null || Number.isNaN(price)) return
      onPickPointRef.current({ time: unix, price: Number(price) })
    }
    chart.subscribeClick(onClick)

    const onThemeChange = () => {
      const next = readChartColors()
      applyChartTheme(chart, seriesBag, next)
      setColors(next)
      const markers: SeriesMarker<Time>[] = signalsCacheRef.current.map((s) => {
        const isLong = s.kind === 'tk_long' || s.kind === 'brk_long'
        return {
          time: ts(s.time),
          position: isLong ? 'belowBar' : 'aboveBar',
          color: isLong ? next.bull : next.bear,
          shape: isLong ? 'arrowUp' : 'arrowDown',
          text: isLong ? 'VOL↑' : 'VOL↓',
        }
      })
      markersRef.current?.setMarkers(layersRef.current.signals ? markers : [])
    }
    window.addEventListener(THEME_CHANGE_EVENT, onThemeChange)

    return () => {
      window.removeEventListener(THEME_CHANGE_EVENT, onThemeChange)
      chart.unsubscribeCrosshairMove(onMove)
      chart.unsubscribeClick(onClick)
      ro.disconnect()
      chart.remove()
      chartRef.current = null
      seriesRef.current = null
      markersRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const chart = chartRef.current
    const series = seriesRef.current
    if (!chart || !series || candles.length === 0 || !symbol) return

    let cancelled = false
    setOverlaysReady(false)
    setOverlayError(null)

    // Prix seul immédiatement — overlays après réponse moteur.
    series.candle.setData(
      candles.map((c) => ({
        time: ts(c.time),
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })),
    )
    series.tenkan.setData([])
    series.kijun.setData([])
    series.spanA.setData([])
    series.spanB.setData([])
    series.cloudUpper.setData([])
    series.cloudLower.setData([])
    series.volume.setData(
      candles.map((c) => ({
        time: ts(c.time),
        value: c.volume,
        color: volumeBarColor(c.open, c.close, colors),
      })),
    )
    chart.timeScale().fitContent()

    void (async () => {
      try {
        const settings = await getSettings().catch(() => null)
        const ichiParams = { ...DEFAULT_ICHI, ...(settings?.ichimokuParams ?? {}) }
        const volParams = { ...DEFAULT_VOL, ...(settings?.volumeParams ?? {}) }
        const { ichi, rvol, projection } = await fetchChartOverlays(
          symbol,
          timeframe,
          candles,
          ichiParams,
          volParams,
        )
        if (cancelled) return

        const { volumes, signals } = buildVolumePulse(candles, ichi, rvol)
        onSignals?.(signals)

        const bySignal = new Map(signals.map((s) => [s.time, s]))
        const map = new Map<number, HoverPoint>()
        const ichiByTime = new Map(ichi.map((p) => [p.time, p]))
        const volByTime = new Map(volumes.map((v) => [v.time, v]))
        for (const c of candles) {
          const ip = ichiByTime.get(c.time)
          const vp = volByTime.get(c.time)
          if (!ip || !vp) continue
          map.set(c.time, {
            time: c.time,
            candle: c,
            ichi: ip,
            volume: vp,
            signal: bySignal.get(c.time) ?? null,
            bias: biasFromIchi(ip.aboveCloud, ip.belowCloud),
          })
        }
        hoverMapRef.current = map
        signalsCacheRef.current = signals

        series.tenkan.setData(asLine(ichi.map((p) => ({ time: p.time, value: p.tenkan }))))
        series.kijun.setData(asLine(ichi.map((p) => ({ time: p.time, value: p.kijun }))))
        const spanPairs = projection
          .map((p) => {
            if (p.senkouA == null || p.senkouB == null) return null
            return {
              time: ts(p.time),
              a: p.senkouA,
              b: p.senkouB,
            }
          })
          .filter((p): p is { time: UTCTimestamp; a: number; b: number } => p != null)
        series.spanA.setData(spanPairs.map((p) => ({ time: p.time, value: p.a })))
        series.spanB.setData(spanPairs.map((p) => ({ time: p.time, value: p.b })))
        // Cloud fill: upper=max(A,B) cloud color, lower=min(A,B) punches bg hole
        series.cloudUpper.setData(
          spanPairs.map((p) => ({ time: p.time, value: Math.max(p.a, p.b) })),
        )
        series.cloudLower.setData(
          spanPairs.map((p) => ({ time: p.time, value: Math.min(p.a, p.b) })),
        )
        const candleByTime = new Map(candles.map((c) => [c.time, c]))
        series.volume.setData(
          volumes.map((v) => {
            const c = candleByTime.get(v.time)
            return {
              time: ts(v.time),
              value: v.volume,
              color: c
                ? volumeBarColor(c.open, c.close, colors)
                : withAlpha(colors.weak, 0.28),
            }
          }),
        )

        const lastIchi = ichi[ichi.length - 1]
        const lastVol = volumes[volumes.length - 1]
        if (lastIchi) {
          onLive?.({
            bias: biasFromIchi(lastIchi.aboveCloud, lastIchi.belowCloud),
            rvol: lastVol?.rvol ?? 0,
          })
        }
        setOverlaysReady(true)
      } catch (err: unknown) {
        if (cancelled) return
        const msg = err instanceof Error ? err.message : 'Overlays moteur indisponibles'
        setOverlayError(msg)
        setOverlaysReady(false)
        onSignals?.([])
        onLive?.({ bias: 'neutral', rvol: 0 })
      }
    })()

    return () => {
      cancelled = true
    }
  }, [candles, symbol, timeframe, onSignals, onLive, colors])

  useEffect(() => {
    const series = seriesRef.current
    if (!series) return
    const showOverlays = overlaysReady && !overlayError
    series.candle.applyOptions({ visible: layers.candles })
    series.tenkan.applyOptions({ visible: showOverlays && layers.tenkan })
    series.kijun.applyOptions({ visible: showOverlays && layers.kijun })
    series.spanA.applyOptions({ visible: showOverlays && layers.spanA })
    series.spanB.applyOptions({ visible: showOverlays && layers.spanB })
    const cloudOn = showOverlays && layers.spanA && layers.spanB
    series.cloudUpper.applyOptions({ visible: cloudOn })
    series.cloudLower.applyOptions({ visible: cloudOn })
    series.volume.applyOptions({ visible: layers.volume })

    const markers: SeriesMarker<Time>[] = [
      ...(layers.signals && showOverlays
        ? signalsCacheRef.current.map((s) => {
            const isLong = s.kind === 'tk_long' || s.kind === 'brk_long'
            return {
              time: ts(s.time),
              position: isLong ? ('belowBar' as const) : ('aboveBar' as const),
              color: isLong ? colors.bull : colors.bear,
              shape: isLong ? ('arrowUp' as const) : ('arrowDown' as const),
              text: isLong ? 'VOL↑' : 'VOL↓',
            }
          })
        : []),
      ...(layers.structure ? structureMarkersRef.current : []),
    ]
    markersRef.current?.setMarkers(markers)
  }, [layers, candles, colors, overlaysReady, overlayError, chartObjects])

  // Overlays moteur via ChartObjects : zones = 2 price lines, trendlines = 2-point series.
  useEffect(() => {
    const filtered = filterObjectsByLayers(chartObjects, prefs)
    const showObjects = OBJECT_LAYER_KEYS.some((k) => prefs[k])
    structureMarkersRef.current = renderChartObjects(
      chartRef.current,
      seriesRef.current,
      priceLinesRef,
      trendSeriesRef,
      filtered,
      showObjects,
      colors,
    )
    const showOverlays = overlaysReady && !overlayError
    const volMarkers: SeriesMarker<Time>[] =
      layers.signals && showOverlays
        ? signalsCacheRef.current.map((s) => {
            const isLong = s.kind === 'tk_long' || s.kind === 'brk_long'
            return {
              time: ts(s.time),
              position: isLong ? ('belowBar' as const) : ('aboveBar' as const),
              color: isLong ? colors.bull : colors.bear,
              shape: isLong ? ('arrowUp' as const) : ('arrowDown' as const),
              text: isLong ? 'VOL↑' : 'VOL↓',
            }
          })
        : []
    markersRef.current?.setMarkers([
      ...volMarkers,
      ...structureMarkersRef.current,
    ])
  }, [chartObjects, layers.signals, colors, candles, overlaysReady, overlayError, prefs])

  const p = tip.point
  const up = p ? p.candle.close >= p.candle.open : false

  const onVolDragStart = (e: ReactPointerEvent<HTMLDivElement>) => {
    e.preventDefault()
    const startY = e.clientY
    const startH = volumeHeight
    const onMove = (ev: PointerEvent) => {
      const delta = startY - ev.clientY
      const next = Math.max(40, Math.min(280, startH + delta))
      onVolumeHeightChange?.(next)
    }
    const onUp = () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
    }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
  }

  return (
    <div className={`chart-wrap${pickMode ? ' is-pick-mode' : ''}`} ref={wrapRef}>
      {overlayError && (
        <p className="muted chart-overlay-msg" role="status">
          Prix seul — overlays moteur indisponibles ({overlayError})
        </p>
      )}
      {!overlayError && !overlaysReady && candles.length > 0 && (
        <p className="muted chart-overlay-msg" role="status">
          Chargement des overlays moteur…
        </p>
      )}
      <div className="chart-host" ref={hostRef} />
      <div
        className="chart-vol-resize"
        role="separator"
        aria-orientation="horizontal"
        aria-label="Redimensionner le volume"
        title="Glisser pour redimensionner le volume"
        onPointerDown={onVolDragStart}
      />
      {tip.visible && p && (
        <div
          className="chart-tip"
          style={{ transform: `translate(${tip.x}px, ${tip.y}px)` }}
          role="tooltip"
        >
          <header>
            <strong>{new Date(p.time * 1000).toLocaleString()}</strong>
            <span className={`bias bias-${p.bias}`}>{p.bias}</span>
          </header>

          <div className="tip-section">
            <h4>Prix</h4>
            <dl>
              <div><dt>O</dt><dd className="mono">{fmtPrice(p.candle.open)}</dd></div>
              <div><dt>H</dt><dd className="mono">{fmtPrice(p.candle.high)}</dd></div>
              <div><dt>L</dt><dd className="mono">{fmtPrice(p.candle.low)}</dd></div>
              <div>
                <dt>C</dt>
                <dd className={`mono ${up ? 'up' : 'down'}`}>{fmtPrice(p.candle.close)}</dd>
              </div>
            </dl>
          </div>

          <div className="tip-section">
            <h4>Ichimoku</h4>
            <dl>
              <div>
                <dt><i style={{ background: colors.tenkan }} /> Tenkan</dt>
                <dd className="mono">{fmtPrice(p.ichi.tenkan)}</dd>
              </div>
              <div>
                <dt><i style={{ background: colors.kijun }} /> Kijun</dt>
                <dd className="mono">{fmtPrice(p.ichi.kijun)}</dd>
              </div>
              <div>
                <dt><i style={{ background: colors.spanA }} /> Span A</dt>
                <dd className="mono">{fmtPrice(p.ichi.senkouA)}</dd>
              </div>
              <div>
                <dt><i style={{ background: colors.spanB }} /> Span B</dt>
                <dd className="mono">{fmtPrice(p.ichi.senkouB)}</dd>
              </div>
              <div>
                <dt>Cloud</dt>
                <dd>
                  {p.ichi.aboveCloud ? 'au-dessus' : p.ichi.belowCloud ? 'en-dessous' : 'dans le cloud'}
                </dd>
              </div>
            </dl>
          </div>

          <div className="tip-section">
            <h4>Volume</h4>
            <dl>
              <div><dt>Vol</dt><dd className="mono">{fmtVol(p.volume.volume)}</dd></div>
              <div><dt>Moy</dt><dd className="mono">{fmtVol(p.volume.volAvg)}</dd></div>
              <div>
                <dt>RVOL</dt>
                <dd className={`mono ${p.volume.confirmed ? 'up' : ''}`}>
                  {p.volume.rvol.toFixed(2)}×
                  {p.volume.confirmed ? ' ✓' : ''}
                  {p.volume.spike ? ' spike' : ''}
                </dd>
              </div>
            </dl>
          </div>

          {p.signal && (
            <div className="tip-signal">
              <span className="sig-chip">{signalLabel(p.signal.kind)}</span>
              <span className="mono">{p.signal.rvol.toFixed(2)}×</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
