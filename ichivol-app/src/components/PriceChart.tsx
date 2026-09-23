import { useEffect, useRef, useState } from 'react'
import {
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
  chartObjectMarkers,
  chartObjectTrendlines,
  chartObjectZones,
  type ChartObject,
} from '../lib/chartObjects'
import { type ChartColors, readChartColors } from '../lib/chartColors'
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

interface Props {
  candles: Candle[]
  symbol: string
  timeframe: Interval | string
  onSignals?: (signals: Signal[]) => void
  onLive?: (live: { bias: 'bull' | 'bear' | 'neutral'; rvol: number }) => void
  /** ChartObjects moteur (zones / trendlines / markers) — couche Structure. */
  chartObjects?: ChartObject[] | null
}

type SeriesBag = {
  candle: ISeriesApi<'Candlestick'>
  tenkan: ISeriesApi<'Line'>
  kijun: ISeriesApi<'Line'>
  spanA: ISeriesApi<'Line'>
  spanB: ISeriesApi<'Line'>
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

const DEFAULT_LAYERS: LayerVis = {
  candles: true,
  tenkan: true,
  kijun: true,
  spanA: true,
  spanB: true,
  volume: true,
  signals: true,
  structure: true,
}

function buildLegend(colors: ChartColors): { key: LayerKey; label: string; color: string; color2?: string }[] {
  return [
    { key: 'candles', label: 'Bougies', color: colors.bull, color2: colors.bear },
    { key: 'tenkan', label: 'Tenkan', color: colors.tenkan },
    { key: 'kijun', label: 'Kijun', color: colors.kijun },
    { key: 'spanA', label: 'Span A', color: colors.spanA },
    { key: 'spanB', label: 'Span B', color: colors.spanB },
    { key: 'volume', label: 'Volume', color: colors.bull, color2: colors.bear },
    { key: 'signals', label: 'Signaux', color: colors.neutral },
    { key: 'structure', label: 'Structure', color: colors.bull, color2: colors.bear },
  ]
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
  chart.applyOptions({
    layout: {
      background: { type: ColorType.Solid, color: 'transparent' },
      textColor: colors.muted,
      fontFamily: "'IBM Plex Sans', system-ui, sans-serif",
    },
    grid: {
      vertLines: { color: `${colors.border}a6` },
      horzLines: { color: `${colors.border}a6` },
    },
    crosshair: {
      mode: 1,
      vertLine: { color: `${colors.muted}73`, labelBackgroundColor: colors.background },
      horzLine: { color: `${colors.muted}73`, labelBackgroundColor: colors.background },
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
  series.tenkan.applyOptions({ color: colors.tenkan })
  series.kijun.applyOptions({ color: colors.kijun })
  series.spanA.applyOptions({ color: colors.spanA })
  series.spanB.applyOptions({ color: colors.spanB })
}

/** Render ENGINE ChartObjects with visual parity to the former Structure overlay. */
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
    const label = z.label || `${z.side === 'support' ? 'S' : 'R'} ×${z.touch_count}`
    for (const [price, title] of [[z.high, label], [z.low, '']] as const) {
      priceLinesRef.current.push(
        series.candle.createPriceLine({
          price,
          color: `${color}b3`,
          lineWidth: 1,
          lineStyle: LineStyle.Dotted,
          axisLabelVisible: title !== '',
          title,
        }),
      )
    }
  }

  for (const t of chartObjectTrendlines(objects)) {
    const color = t.side === 'support' ? colors.bull : colors.bear
    const line = chart.addSeries(
      LineSeries,
      {
        color,
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
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

  // MARKER (breakouts): circle markers — merged with volume signals by caller.
  return chartObjectMarkers(objects).map((m) => {
    const bullish = m.side === 'resistance' // break above resistance
    return {
      time: ts(m.time),
      position: bullish ? ('belowBar' as const) : ('aboveBar' as const),
      color: bullish ? colors.bull : colors.bear,
      shape: 'circle' as const,
      text: m.label,
    }
  })
}

export function PriceChart({ candles, symbol, timeframe, onSignals, onLive, chartObjects }: Props) {
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
  const layersRef = useRef<LayerVis>(DEFAULT_LAYERS)
  const [colors, setColors] = useState<ChartColors>(() => readChartColors())
  const [layers, setLayers] = useState<LayerVis>(DEFAULT_LAYERS)
  const [overlayError, setOverlayError] = useState<string | null>(null)
  const [overlaysReady, setOverlaysReady] = useState(false)

  useEffect(() => {
    layersRef.current = layers
  }, [layers])
  const [tip, setTip] = useState<TipState>({
    visible: false,
    x: 0,
    y: 0,
    point: null,
  })

  const toggleLayer = (key: LayerKey) => {
    setLayers((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  useEffect(() => {
    const el = hostRef.current
    if (!el) return
    const initialColors = readChartColors()

    const chart = createChart(el, {
      width: el.clientWidth || 800,
      height: el.clientHeight || 480,
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false },
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
    const candle = chart.addSeries(CandlestickSeries, { ...seriesOpts }, 0)
    const tenkan = chart.addSeries(LineSeries, { lineWidth: 2, ...seriesOpts }, 0)
    const kijun = chart.addSeries(LineSeries, { lineWidth: 2, ...seriesOpts }, 0)
    const spanA = chart.addSeries(LineSeries, { lineWidth: 1, lineStyle: LineStyle.Dashed, ...seriesOpts }, 0)
    const spanB = chart.addSeries(LineSeries, { lineWidth: 1, lineStyle: LineStyle.Dashed, ...seriesOpts }, 0)
    const volume = chart.addSeries(
      HistogramSeries,
      { priceFormat: { type: 'volume' }, priceScaleId: '', ...seriesOpts },
      1,
    )
    volume.priceScale().applyOptions({ scaleMargins: { top: 0.2, bottom: 0 } })
    const panes = chart.panes()
    if (panes[1]) panes[1].setHeight(110)

    const seriesBag: SeriesBag = { candle, tenkan, kijun, spanA, spanB, volume }
    applyChartTheme(chart, seriesBag, initialColors)

    markersRef.current = createSeriesMarkers(candle, [])
    chartRef.current = chart
    seriesRef.current = seriesBag
    setColors(initialColors)

    const onMove = (param: MouseEventParams<Time>) => {
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
    series.volume.setData(
      candles.map((c) => ({ time: ts(c.time), value: c.volume, color: colors.weak })),
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
        series.spanA.setData(asLine(projection.map((p) => ({ time: p.time, value: p.senkouA }))))
        series.spanB.setData(asLine(projection.map((p) => ({ time: p.time, value: p.senkouB }))))
        series.volume.setData(
          volumes.map((v) => ({ time: ts(v.time), value: v.volume, color: v.color })),
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
  }, [candles, symbol, timeframe, onSignals, onLive, colors.weak])

  useEffect(() => {
    const series = seriesRef.current
    if (!series) return
    const showOverlays = overlaysReady && !overlayError
    series.candle.applyOptions({ visible: layers.candles })
    series.tenkan.applyOptions({ visible: showOverlays && layers.tenkan })
    series.kijun.applyOptions({ visible: showOverlays && layers.kijun })
    series.spanA.applyOptions({ visible: showOverlays && layers.spanA })
    series.spanB.applyOptions({ visible: showOverlays && layers.spanB })
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
    structureMarkersRef.current = renderChartObjects(
      chartRef.current,
      seriesRef.current,
      priceLinesRef,
      trendSeriesRef,
      chartObjects,
      layers.structure,
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
      ...(layers.structure ? structureMarkersRef.current : []),
    ])
  }, [chartObjects, layers.structure, layers.signals, colors, candles, overlaysReady, overlayError])

  const p = tip.point
  const up = p ? p.candle.close >= p.candle.open : false
  const legend = buildLegend(colors)

  return (
    <div className="chart-wrap" ref={wrapRef}>
      <div className="chart-legend" role="toolbar" aria-label="Couches du graphique">
        {legend.map((item) => (
          <button
            key={item.key}
            type="button"
            className={`legend-chip${layers[item.key] ? ' is-on' : ' is-off'}`}
            aria-pressed={layers[item.key]}
            title={layers[item.key] ? `Masquer ${item.label}` : `Afficher ${item.label}`}
            onClick={() => toggleLayer(item.key)}
          >
            <span className="legend-dots" aria-hidden="true">
              <i style={{ background: item.color }} />
              {item.color2 && <i style={{ background: item.color2 }} />}
            </span>
            {item.label}
          </button>
        ))}
        <span className="legend-hint">Clique pour afficher / masquer</span>
      </div>
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
