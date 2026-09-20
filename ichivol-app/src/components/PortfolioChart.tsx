import { useEffect, useMemo, useRef, useState } from 'react'
import {
  AreaSeries,
  BaselineSeries,
  CandlestickSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  HistogramSeries,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type MouseEventParams,
  type SeriesMarker,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts'
import { readChartColors } from '../lib/chartColors'
import type { PaperOrderRow } from '../lib/paper'
import { THEME_CHANGE_EVENT } from '../lib/theme'
import { assetName, eur, signedEur } from '../lib/tradeStory'

type Point = { t: string; equity: number }

type LayerKey = 'candles' | 'equity' | 'baseline' | 'delta' | 'trades'

type Hover = {
  time: number
  equity: number
  prev: number
  delta: number
  deltaPct: number
  vsInitial: number
  vsInitialPct: number
  trades: PaperOrderRow[]
}

function toUnix(iso: string): number | null {
  const ms = Date.parse(iso)
  if (!Number.isFinite(ms)) return null
  return Math.floor(ms / 1000)
}

function fmtWhen(unix: number): string {
  return new Date(unix * 1000).toLocaleString('fr-FR', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * Graphique portefeuille façon TradingView (lightweight-charts) :
 * bougies synthétiques, aire colorée, baseline départ, volume de variation,
 * marqueurs d’ordres, bulle HTML au survol (pas de pastilles noires).
 */
export function PortfolioChart({
  points,
  initial,
  orders = [],
}: {
  points: Point[]
  initial: number
  orders?: PaperOrderRow[]
}) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const hostRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candleRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const areaRef = useRef<ISeriesApi<'Area'> | null>(null)
  const baseRef = useRef<ISeriesApi<'Baseline'> | null>(null)
  const deltaRef = useRef<ISeriesApi<'Histogram'> | null>(null)
  const markersApiRef = useRef<ReturnType<typeof createSeriesMarkers<Time>> | null>(null)
  const hoverMap = useRef<Map<number, Hover>>(new Map())
  const layersRef = useRef<Record<LayerKey, boolean>>({
    candles: true,
    equity: true,
    baseline: true,
    delta: true,
    trades: true,
  })
  const preparedMarkersRef = useRef<SeriesMarker<Time>[]>([])

  const [layers, setLayers] = useState(layersRef.current)
  const [tip, setTip] = useState<{ visible: boolean; x: number; y: number; point: Hover | null }>({
    visible: false,
    x: 0,
    y: 0,
    point: null,
  })

  const prepared = useMemo(() => {
    const cleaned = points
      .map((p) => {
        const u = toUnix(p.t)
        if (u == null || !Number.isFinite(p.equity)) return null
        return { time: u as UTCTimestamp, equity: p.equity }
      })
      .filter((x): x is { time: UTCTimestamp; equity: number } => x != null)
      // lightweight-charts exige des timestamps croissants uniques
      .sort((a, b) => Number(a.time) - Number(b.time))
      .filter((p, i, arr) => i === 0 || p.time !== arr[i - 1].time)

    if (cleaned.length === 0) return null

    const candles = cleaned.map((p, i) => {
      const open = i === 0 ? initial : cleaned[i - 1].equity
      const close = p.equity
      return {
        time: p.time,
        open,
        high: Math.max(open, close),
        low: Math.min(open, close),
        close,
      }
    })

    const area = cleaned.map((p) => ({ time: p.time, value: p.equity }))
    const baseline = cleaned.map((p) => ({ time: p.time, value: p.equity }))
    const delta = cleaned.map((p, i) => {
      const prev = i === 0 ? initial : cleaned[i - 1].equity
      const d = p.equity - prev
      return {
        time: p.time,
        value: Math.abs(d),
        color: d >= 0 ? undefined : undefined, // set later with theme
        _signed: d,
      }
    })

    const map = new Map<number, Hover>()
    for (let i = 0; i < cleaned.length; i++) {
      const p = cleaned[i]
      const prev = i === 0 ? initial : cleaned[i - 1].equity
      const d = p.equity - prev
      const t = Number(p.time)
      map.set(t, {
        time: t,
        equity: p.equity,
        prev,
        delta: d,
        deltaPct: prev ? d / prev : 0,
        vsInitial: p.equity - initial,
        vsInitialPct: initial ? (p.equity - initial) / initial : 0,
        trades: [],
      })
    }

    for (const o of orders) {
      const u = toUnix(o.time)
      if (u == null) continue
      // rattacher à la barre la plus proche (≤ 6h)
      let best: number | null = null
      let bestDist = Infinity
      for (const t of map.keys()) {
        const dist = Math.abs(t - u)
        if (dist < bestDist) {
          bestDist = dist
          best = t
        }
      }
      if (best != null && bestDist <= 6 * 3600) {
        map.get(best)!.trades.push(o)
      }
    }

    const markers: SeriesMarker<Time>[] = []
    for (const o of orders) {
      const u = toUnix(o.time)
      if (u == null) continue
      const isBuy = o.side === 'BUY' || o.reason === 'open'
      const isClose = o.reason !== 'open' && o.reason != null
      markers.push({
        time: u as UTCTimestamp,
        position: isBuy && !isClose ? 'belowBar' : 'aboveBar',
        color: isClose ? '#888' : isBuy ? '#16a34a' : '#dc2626',
        shape: isClose ? 'circle' : isBuy ? 'arrowUp' : 'arrowDown',
        text: assetName(o.symbol),
      })
    }

    return { candles, area, baseline, delta, map, markers, last: cleaned[cleaned.length - 1].equity }
  }, [points, initial, orders])

  useEffect(() => {
    layersRef.current = layers
    const c = candleRef.current
    const a = areaRef.current
    const b = baseRef.current
    const d = deltaRef.current
    if (c) c.applyOptions({ visible: layers.candles })
    if (a) a.applyOptions({ visible: layers.equity })
    if (b) b.applyOptions({ visible: layers.baseline })
    if (d) d.applyOptions({ visible: layers.delta })
    markersApiRef.current?.setMarkers(layers.trades ? preparedMarkersRef.current : [])
  }, [layers])

  useEffect(() => {
    const el = hostRef.current
    if (!el || !prepared) return

    const colors = readChartColors()
    const chart = createChart(el, {
      width: el.clientWidth || 800,
      height: 360,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: colors.muted || '#888',
      },
      grid: {
        vertLines: { color: 'rgba(128,128,128,0.08)' },
        horzLines: { color: 'rgba(128,128,128,0.12)' },
      },
      crosshair: {
        mode: 0,
        vertLine: {
          color: 'rgba(128,128,128,0.35)',
          labelBackgroundColor: colors.foreground || '#333',
        },
        horzLine: {
          color: 'rgba(128,128,128,0.35)',
          labelBackgroundColor: colors.foreground || '#333',
        },
      },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false },
    })

    const seriesOpts = {
      lastValueVisible: true,
      priceLineVisible: false,
      crosshairMarkerVisible: true,
      crosshairMarkerRadius: 5,
      crosshairMarkerBorderWidth: 2,
    } as const

    const candles = chart.addSeries(
      CandlestickSeries,
      {
        ...seriesOpts,
        upColor: colors.bull,
        downColor: colors.bear,
        wickUpColor: colors.bull,
        wickDownColor: colors.bear,
        borderVisible: false,
        visible: layersRef.current.candles,
      },
      0,
    )

    const area = chart.addSeries(
      AreaSeries,
      {
        ...seriesOpts,
        lineWidth: 2,
        lineColor: colors.bull,
        topColor: `${colors.bull}55`,
        bottomColor: `${colors.bull}05`,
        visible: layersRef.current.equity,
      },
      0,
    )

    const baseline = chart.addSeries(
      BaselineSeries,
      {
        ...seriesOpts,
        baseValue: { type: 'price', price: initial },
        topLineColor: colors.bull,
        topFillColor1: `${colors.bull}40`,
        topFillColor2: `${colors.bull}08`,
        bottomLineColor: colors.bear,
        bottomFillColor1: `${colors.bear}08`,
        bottomFillColor2: `${colors.bear}40`,
        lineWidth: 2,
        visible: layersRef.current.baseline,
      },
      0,
    )

    const delta = chart.addSeries(
      HistogramSeries,
      {
        priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
        priceScaleId: '',
        lastValueVisible: false,
        priceLineVisible: false,
        visible: layersRef.current.delta,
      },
      1,
    )
    delta.priceScale().applyOptions({ scaleMargins: { top: 0.75, bottom: 0 } })
    const panes = chart.panes()
    if (panes[1]) panes[1].setHeight(72)

    candles.createPriceLine({
      price: initial,
      color: colors.muted || '#888',
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: true,
      title: 'Départ',
    })

    chartRef.current = chart
    candleRef.current = candles
    areaRef.current = area
    baseRef.current = baseline
    deltaRef.current = delta
    hoverMap.current = prepared.map
    preparedMarkersRef.current = prepared.markers

    candles.setData(prepared.candles)
    area.setData(prepared.area)
    baseline.setData(prepared.baseline)
    delta.setData(
      prepared.delta.map((d) => ({
        time: d.time,
        value: d.value,
        color: d._signed >= 0 ? `${colors.bull}99` : `${colors.bear}99`,
      })),
    )

    const markersApi = createSeriesMarkers(candles, layersRef.current.trades ? prepared.markers : [])
    markersApiRef.current = markersApi

    const onMove = (param: MouseEventParams<Time>) => {
      if (!param.point || param.point.x < 0 || param.point.y < 0 || !param.time || !wrapRef.current) {
        setTip((prev) => (prev.visible ? { ...prev, visible: false, point: null } : prev))
        return
      }
      const t =
        typeof param.time === 'number'
          ? param.time
          : typeof param.time === 'string'
            ? Date.parse(param.time) / 1000
            : null
      if (t == null) {
        setTip((prev) => (prev.visible ? { ...prev, visible: false, point: null } : prev))
        return
      }
      const point = hoverMap.current.get(t) ?? null
      if (!point) {
        setTip((prev) => (prev.visible ? { ...prev, visible: false, point: null } : prev))
        return
      }
      const wrap = wrapRef.current
      const tipW = 260
      const tipH = 200
      let x = param.point.x + 18
      let y = param.point.y + 18
      if (x + tipW > wrap.clientWidth - 8) x = param.point.x - tipW - 12
      if (y + tipH > wrap.clientHeight - 8) y = Math.max(8, param.point.y - tipH - 8)
      setTip({ visible: true, x: Math.max(8, x), y: Math.max(8, y), point })
    }
    chart.subscribeCrosshairMove(onMove)

    const onResize = () => {
      if (!hostRef.current) return
      chart.applyOptions({ width: hostRef.current.clientWidth })
    }
    onResize()
    window.addEventListener('resize', onResize)

    const onTheme = () => {
      const next = readChartColors()
      chart.applyOptions({ layout: { textColor: next.muted || '#888' } })
      candles.applyOptions({
        upColor: next.bull,
        downColor: next.bear,
        wickUpColor: next.bull,
        wickDownColor: next.bear,
      })
      area.applyOptions({
        lineColor: next.bull,
        topColor: `${next.bull}55`,
        bottomColor: `${next.bull}05`,
      })
      baseline.applyOptions({
        topLineColor: next.bull,
        topFillColor1: `${next.bull}40`,
        topFillColor2: `${next.bull}08`,
        bottomLineColor: next.bear,
        bottomFillColor1: `${next.bear}08`,
        bottomFillColor2: `${next.bear}40`,
      })
      delta.setData(
        prepared.delta.map((d) => ({
          time: d.time,
          value: d.value,
          color: d._signed >= 0 ? `${next.bull}99` : `${next.bear}99`,
        })),
      )
    }
    window.addEventListener(THEME_CHANGE_EVENT, onTheme)

    chart.timeScale().fitContent()

    return () => {
      window.removeEventListener('resize', onResize)
      window.removeEventListener(THEME_CHANGE_EVENT, onTheme)
      markersApi.setMarkers([])
      markersApiRef.current = null
      chart.remove()
      chartRef.current = null
      candleRef.current = null
      areaRef.current = null
      baseRef.current = null
      deltaRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prepared, initial])

  if (!prepared || prepared.candles.length < 2) {
    return (
      <p className="muted broker-curve-empty">
        Pas assez de points encore — la courbe vivante apparaîtra après quelques cycles du moteur.
      </p>
    )
  }

  const up = prepared.last >= initial
  const legend: { key: LayerKey; label: string; color: string; color2?: string }[] = [
    { key: 'candles', label: 'Bougies', color: 'var(--bull)', color2: 'var(--bear)' },
    { key: 'equity', label: 'Aire', color: 'var(--bull)' },
    { key: 'baseline', label: 'vs départ', color: 'var(--bull)', color2: 'var(--bear)' },
    { key: 'delta', label: 'Variation', color: 'var(--neutral)' },
    { key: 'trades', label: 'Ordres', color: 'var(--foreground)' },
  ]

  return (
    <div className="portfolio-chart" ref={wrapRef}>
      <div className="portfolio-chart-toolbar">
        <div className="chart-legend" role="toolbar" aria-label="Couches du portefeuille">
          {legend.map((l) => (
            <button
              key={l.key}
              type="button"
              className={`legend-chip${layers[l.key] ? ' is-on' : ' is-off'}`}
              onClick={() => setLayers((prev) => ({ ...prev, [l.key]: !prev[l.key] }))}
            >
              <span className="legend-dots" aria-hidden>
                <i style={{ background: l.color }} />
                {l.color2 && <i style={{ background: l.color2 }} />}
              </span>
              {l.label}
            </button>
          ))}
        </div>
        <span className={`portfolio-chart-now ${up ? 'up' : 'down'}`}>
          {eur(prepared.last)} · {signedEur(prepared.last - initial)}
        </span>
      </div>
      <div ref={hostRef} className="portfolio-chart-host" />
      {tip.visible && tip.point && (
        <aside
          className="chart-tip portfolio-tip"
          style={{ left: tip.x, top: tip.y }}
          aria-hidden
        >
          <header>
            <strong>{fmtWhen(tip.point.time)}</strong>
            <span className={tip.point.vsInitial >= 0 ? 'up' : 'down'}>
              {signedEur(tip.point.vsInitial)}
            </span>
          </header>
          <div className="tip-section">
            <h4>Portefeuille</h4>
            <dl>
              <div>
                <dt>Valeur</dt>
                <dd>{eur(tip.point.equity)}</dd>
              </div>
              <div>
                <dt>vs barre préc.</dt>
                <dd className={tip.point.delta >= 0 ? 'up' : 'down'}>
                  {signedEur(tip.point.delta)} ({(tip.point.deltaPct * 100).toFixed(2)} %)
                </dd>
              </div>
              <div>
                <dt>vs départ ({eur(initial, 0)})</dt>
                <dd className={tip.point.vsInitial >= 0 ? 'up' : 'down'}>
                  {(tip.point.vsInitialPct * 100).toFixed(2)} %
                </dd>
              </div>
            </dl>
          </div>
          {tip.point.trades.length > 0 && (
            <div className="tip-section">
              <h4>Ordres près de ce point</h4>
              <ul className="portfolio-tip-trades">
                {tip.point.trades.slice(0, 4).map((o) => (
                  <li key={o.id}>
                    <span className={o.side === 'BUY' ? 'up' : 'down'}>
                      {o.side === 'BUY' ? 'Achat' : 'Vente'}
                    </span>{' '}
                    {assetName(o.symbol)} · {eur(o.notional)}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </aside>
      )}
    </div>
  )
}
