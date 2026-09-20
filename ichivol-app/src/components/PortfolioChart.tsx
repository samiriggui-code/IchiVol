import { useEffect, useMemo, useRef, useState } from 'react'
import {
  AreaSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  LineSeries,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type MouseEventParams,
  type SeriesMarker,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts'
import { readChartColors, type ChartColors } from '../lib/chartColors'
import type { PaperOrderRow, PaperOverviewPosition } from '../lib/paper'
import { THEME_CHANGE_EVENT } from '../lib/theme'
import {
  assetName,
  directionWords,
  eur,
  exitReasonLabel,
  price,
  signedEur,
} from '../lib/tradeStory'

type Point = { t: string; equity: number }

export type PortfolioRange = '1h' | '4h' | '1d' | '1w' | '1M'

export const PORTFOLIO_RANGES: { id: PortfolioRange; label: string; bucketSec: number }[] = [
  { id: '1h', label: '1H', bucketSec: 3600 },
  { id: '4h', label: '4H', bucketSec: 4 * 3600 },
  { id: '1d', label: '1D', bucketSec: 86400 },
  { id: '1w', label: '1S', bucketSec: 7 * 86400 },
  { id: '1M', label: '1M', bucketSec: 30 * 86400 },
]

const PALETTE = [
  '#2563eb',
  '#db2777',
  '#ea580c',
  '#7c3aed',
  '#0891b2',
  '#ca8a04',
  '#16a34a',
  '#e11d48',
  '#4f46e5',
  '#0d9488',
]

function colorForSymbol(symbol: string): string {
  let h = 0
  for (let i = 0; i < symbol.length; i++) h = (h * 31 + symbol.charCodeAt(i)) >>> 0
  return PALETTE[h % PALETTE.length]
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

function acquisitionWhy(o: PaperOrderRow): string {
  if (o.reason === 'open') {
    return o.side === 'BUY'
      ? 'Ouverture longue — signal jugé assez fort pour entrer'
      : 'Ouverture short — pari à la baisse validé'
  }
  return exitReasonLabel(o.reason)
}

function sampleSteps(steps: { t: number; v: number }[], t: number): number {
  let v = 0
  for (const s of steps) {
    if (s.t <= t) v = s.v
    else break
  }
  return v
}

function downsample(
  points: { time: number; equity: number }[],
  bucketSec: number,
): { time: UTCTimestamp; value: number }[] {
  if (points.length === 0) return []
  const buckets = new Map<number, number>()
  for (const p of points) {
    const key = Math.floor(p.time / bucketSec) * bucketSec
    buckets.set(key, p.equity)
  }
  return [...buckets.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([t, value]) => ({ time: t as UTCTimestamp, value }))
}

export type PortfolioAsset = {
  symbol: string
  label: string
  color: string
  invested: number
  opens: PaperOrderRow[]
  line: { time: UTCTimestamp; value: number }[]
}

type Hover = {
  time: number
  equity: number
  vsInitial: number
  events: PaperOrderRow[]
  assets: { symbol: string; label: string; color: string; invested: number }[]
}

type LayerVis = Record<string, boolean>

/**
 * Graphique style Marché (même chart-wrap / legend / host) :
 * courbe capital + évolution des sommes investies par actif acquis.
 */
export function PortfolioChart({
  points,
  initial,
  orders = [],
  positions = [],
  range,
  focusSymbol = null,
  onAssetsChange,
}: {
  points: Point[]
  initial: number
  orders?: PaperOrderRow[]
  positions?: PaperOverviewPosition[]
  range: PortfolioRange
  /** Actif mis en avant (ligne plus épaisse) — null = capital. */
  focusSymbol?: string | null
  onAssetsChange?: (assets: PortfolioAsset[]) => void
}) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const hostRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const capitalRef = useRef<ISeriesApi<'Area'> | null>(null)
  const assetSeriesRef = useRef<Map<string, ISeriesApi<'Line'>>>(new Map())
  const markersApiRef = useRef<ReturnType<typeof createSeriesMarkers<Time>> | null>(null)
  const startLineDone = useRef(false)
  const hoverMap = useRef<Map<number, Hover>>(new Map())
  const layersRef = useRef<LayerVis>({ capital: true })
  const focusRef = useRef<string | null>(focusSymbol)
  const colorsRef = useRef<ChartColors>(readChartColors())

  const [colors, setColors] = useState<ChartColors>(() => readChartColors())
  const [layers, setLayers] = useState<LayerVis>({ capital: true })
  const [tip, setTip] = useState<{
    visible: boolean
    x: number
    y: number
    point: Hover | null
  }>({ visible: false, x: 0, y: 0, point: null })

  focusRef.current = focusSymbol

  const model = useMemo(() => {
    const equityRaw = points
      .map((p) => {
        const u = toUnix(p.t)
        if (u == null || !Number.isFinite(p.equity)) return null
        return { time: u, equity: p.equity }
      })
      .filter((x): x is { time: number; equity: number } => x != null)
      .sort((a, b) => a.time - b.time)
      .filter((p, i, arr) => i === 0 || p.time !== arr[i - 1].time)

    const bucket = PORTFOLIO_RANGES.find((r) => r.id === range)?.bucketSec ?? 86400
    let capital = downsample(equityRaw, bucket)
    // Si le bucket écrase tout en 1 point, garder le raw
    if (capital.length < 2 && equityRaw.length >= 2) {
      capital = equityRaw.map((p) => ({ time: p.time as UTCTimestamp, value: p.equity }))
    }

    const sortedOrders = [...orders].sort((a, b) => Date.parse(a.time) - Date.parse(b.time))
    const bySym = new Map<
      string,
      { invested: number; steps: { t: number; v: number }[]; opens: PaperOrderRow[] }
    >()

    for (const o of sortedOrders) {
      const u = toUnix(o.time)
      if (u == null) continue
      let row = bySym.get(o.symbol)
      if (!row) {
        row = { invested: 0, steps: [{ t: u - 1, v: 0 }], opens: [] }
        bySym.set(o.symbol, row)
      }
      if (o.reason === 'open') {
        row.invested += Math.abs(o.notional || 0)
        row.opens.push(o)
      } else {
        row.invested = Math.max(0, row.invested - Math.abs(o.notional || 0))
      }
      row.steps.push({ t: u, v: row.invested })
    }

    for (const p of positions) {
      if (p.status !== 'OPEN' || bySym.has(p.symbol)) continue
      const u = toUnix(p.entry_time) ?? Math.floor(Date.now() / 1000)
      bySym.set(p.symbol, {
        invested: Math.abs(p.notional ?? 0),
        steps: [
          { t: u - 1, v: 0 },
          { t: u, v: Math.abs(p.notional ?? 0) },
        ],
        opens: [],
      })
    }

    const times = capital.map((p) => Number(p.time))
    const assets: PortfolioAsset[] = [...bySym.entries()]
      .map(([symbol, row]) => ({
        symbol,
        label: assetName(symbol),
        color: colorForSymbol(symbol),
        invested: row.invested,
        opens: row.opens,
        line: times.map((t) => ({
          time: t as UTCTimestamp,
          value: sampleSteps(row.steps, t),
        })),
      }))
      .filter((a) => a.line.some((p) => p.value > 0) || a.opens.length > 0 || a.invested > 0)
      .sort((a, b) => b.invested - a.invested || a.label.localeCompare(b.label))

    const map = new Map<number, Hover>()
    for (const c of capital) {
      const t = Number(c.time)
      map.set(t, {
        time: t,
        equity: c.value,
        vsInitial: c.value - initial,
        events: [],
        assets: assets.map((a) => ({
          symbol: a.symbol,
          label: a.label,
          color: a.color,
          invested: sampleSteps(
            a.line.map((p) => ({ t: Number(p.time), v: p.value })),
            t,
          ),
        })),
      })
    }

    for (const o of sortedOrders) {
      const u = toUnix(o.time)
      if (u == null || map.size === 0) continue
      let best: number | null = null
      let bestD = Infinity
      for (const t of map.keys()) {
        const d = Math.abs(t - u)
        if (d < bestD) {
          bestD = d
          best = t
        }
      }
      if (best != null && bestD <= bucket * 2) {
        map.get(best)!.events.push(o)
      }
    }

    const last = capital.length > 0 ? capital[capital.length - 1].value : initial
    return { capital, assets, map, last, nRaw: equityRaw.length }
  }, [points, initial, orders, positions, range])

  useEffect(() => {
    onAssetsChange?.(model.assets)
  }, [model.assets, onAssetsChange])

  // Init layer keys when assets appear
  useEffect(() => {
    setLayers((prev) => {
      const next: LayerVis = { capital: prev.capital !== false }
      for (const a of model.assets) {
        next[a.symbol] = prev[a.symbol] !== false
      }
      layersRef.current = next
      return next
    })
  }, [model.assets])

  useEffect(() => {
    layersRef.current = layers
  }, [layers])

  // Mount chart once (like PriceChart)
  useEffect(() => {
    const el = hostRef.current
    if (!el) return

    const initialColors = readChartColors()
    colorsRef.current = initialColors
    setColors(initialColors)

    const chart = createChart(el, {
      width: el.clientWidth || 800,
      height: el.clientHeight || 420,
      rightPriceScale: { borderVisible: false },
      leftPriceScale: { visible: true, borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false },
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: initialColors.muted || '#888',
        fontFamily: "'IBM Plex Sans', system-ui, sans-serif",
      },
      grid: {
        vertLines: { color: `${initialColors.border}a6` },
        horzLines: { color: `${initialColors.border}a6` },
      },
      crosshair: {
        mode: 1,
        vertLine: { color: `${initialColors.muted}73`, labelBackgroundColor: initialColors.background },
        horzLine: { color: `${initialColors.muted}73`, labelBackgroundColor: initialColors.background },
      },
    })

    const capital = chart.addSeries(AreaSeries, {
      lineWidth: 3,
      lineColor: initialColors.bull || '#16a34a',
      topColor: `${initialColors.bull || '#16a34a'}55`,
      bottomColor: `${initialColors.bull || '#16a34a'}08`,
      lastValueVisible: true,
      priceLineVisible: false,
      priceScaleId: 'right',
      title: 'Capital',
    })
    capital.priceScale().applyOptions({ scaleMargins: { top: 0.08, bottom: 0.12 } })

    markersApiRef.current = createSeriesMarkers(capital, [])
    chartRef.current = chart
    capitalRef.current = capital

    const ro = new ResizeObserver(() => {
      if (!hostRef.current) return
      chart.applyOptions({
        width: hostRef.current.clientWidth,
        height: Math.max(hostRef.current.clientHeight, 280),
      })
    })
    ro.observe(el)

    const onMove = (param: MouseEventParams<Time>) => {
      if (!param.point || !param.time || param.point.x < 0 || !wrapRef.current) {
        setTip((prev) => (prev.visible ? { ...prev, visible: false, point: null } : prev))
        return
      }
      const t = typeof param.time === 'number' ? param.time : null
      if (t == null) {
        setTip((prev) => (prev.visible ? { ...prev, visible: false, point: null } : prev))
        return
      }
      let point = hoverMap.current.get(t) ?? null
      if (!point) {
        let best: number | null = null
        let bestD = Infinity
        for (const k of hoverMap.current.keys()) {
          const d = Math.abs(k - t)
          if (d < bestD) {
            bestD = d
            best = k
          }
        }
        if (best != null && bestD < 7 * 86400) point = hoverMap.current.get(best) ?? null
      }
      if (!point) {
        setTip((prev) => (prev.visible ? { ...prev, visible: false, point: null } : prev))
        return
      }
      const wrap = wrapRef.current
      const tipW = 280
      const tipH = 260
      let x = param.point.x + 16
      let y = param.point.y + 16
      if (x + tipW > wrap.clientWidth - 8) x = param.point.x - tipW - 12
      if (y + tipH > wrap.clientHeight - 8) y = Math.max(8, param.point.y - tipH - 8)
      setTip({ visible: true, x: Math.max(8, x), y: Math.max(8, y), point })
    }
    chart.subscribeCrosshairMove(onMove)

    const onTheme = () => {
      const next = readChartColors()
      colorsRef.current = next
      setColors(next)
      chart.applyOptions({
        layout: { textColor: next.muted || '#888' },
        grid: {
          vertLines: { color: `${next.border}a6` },
          horzLines: { color: `${next.border}a6` },
        },
      })
      capital.applyOptions({
        lineColor: next.bull || '#16a34a',
        topColor: `${next.bull || '#16a34a'}55`,
        bottomColor: `${next.bull || '#16a34a'}08`,
      })
    }
    window.addEventListener(THEME_CHANGE_EVENT, onTheme)

    return () => {
      window.removeEventListener(THEME_CHANGE_EVENT, onTheme)
      chart.unsubscribeCrosshairMove(onMove)
      ro.disconnect()
      markersApiRef.current?.setMarkers([])
      chart.remove()
      chartRef.current = null
      capitalRef.current = null
      assetSeriesRef.current.clear()
      markersApiRef.current = null
      startLineDone.current = false
    }
  }, [])

  // Push data whenever model changes
  useEffect(() => {
    const chart = chartRef.current
    const capital = capitalRef.current
    if (!chart || !capital) return

    if (model.capital.length < 2) {
      capital.setData([])
      for (const s of assetSeriesRef.current.values()) s.setData([])
      markersApiRef.current?.setMarkers([])
      return
    }

    capital.setData(model.capital)
    capital.applyOptions({ visible: layersRef.current.capital !== false })
    if (!startLineDone.current) {
      capital.createPriceLine({
        price: initial,
        color: colorsRef.current.muted || '#888',
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: 'Départ',
      })
      startLineDone.current = true
    }

    hoverMap.current = model.map

    const wanted = new Set(model.assets.map((a) => a.symbol))
    for (const [sym, series] of assetSeriesRef.current) {
      if (!wanted.has(sym)) {
        chart.removeSeries(series)
        assetSeriesRef.current.delete(sym)
      }
    }

    for (const a of model.assets) {
      let series = assetSeriesRef.current.get(a.symbol)
      if (!series) {
        series = chart.addSeries(LineSeries, {
          color: a.color,
          lineWidth: focusRef.current === a.symbol ? 3 : 2,
          lastValueVisible: true,
          priceLineVisible: false,
          priceScaleId: 'left',
          title: a.label,
        })
        series.priceScale().applyOptions({ scaleMargins: { top: 0.15, bottom: 0.05 } })
        assetSeriesRef.current.set(a.symbol, series)
      }
      const on = layersRef.current[a.symbol] !== false
      series.applyOptions({
        visible: on,
        color: a.color,
        lineWidth: focusRef.current === a.symbol ? 3 : 2,
        title: a.label,
      })
      series.setData(a.line)
    }

    const markers: SeriesMarker<Time>[] = []
    for (const a of model.assets) {
      if (layersRef.current[a.symbol] === false) continue
      if (focusRef.current && focusRef.current !== a.symbol) continue
      for (const o of a.opens) {
        const u = toUnix(o.time)
        if (u == null) continue
        markers.push({
          time: u as UTCTimestamp,
          position: 'belowBar',
          color: a.color,
          shape: 'arrowUp',
          text: a.label.slice(0, 6),
        })
      }
    }
    markersApiRef.current?.setMarkers(markers)
    chart.timeScale().fitContent()
  }, [model, initial])

  // Layer / focus visibility without full data rebuild
  useEffect(() => {
    capitalRef.current?.applyOptions({ visible: layers.capital !== false })
    for (const [sym, series] of assetSeriesRef.current) {
      series.applyOptions({
        visible: layers[sym] !== false,
        lineWidth: focusSymbol === sym ? 3 : 2,
      })
    }
    const markers: SeriesMarker<Time>[] = []
    for (const a of model.assets) {
      if (layers[a.symbol] === false) continue
      if (focusSymbol && focusSymbol !== a.symbol) continue
      for (const o of a.opens) {
        const u = toUnix(o.time)
        if (u == null) continue
        markers.push({
          time: u as UTCTimestamp,
          position: 'belowBar',
          color: a.color,
          shape: 'arrowUp',
          text: a.label.slice(0, 6),
        })
      }
    }
    markersApiRef.current?.setMarkers(markers)
  }, [layers, focusSymbol, model.assets])

  if (model.capital.length < 2) {
    return (
      <div className="chart-wrap">
        <p className="muted broker-curve-empty">
          Pas assez d’historique ({model.nRaw} point{model.nRaw > 1 ? 's' : ''}) — la courbe
          apparaîtra après les prochains cycles du moteur.
        </p>
      </div>
    )
  }

  const toggle = (key: string) => {
    setLayers((prev) => {
      const next = { ...prev, [key]: !(prev[key] !== false) }
      layersRef.current = next
      return next
    })
  }

  return (
    <div className="chart-wrap" ref={wrapRef}>
      <div className="chart-legend" role="toolbar" aria-label="Couches du graphique">
        <button
          type="button"
          className={`legend-chip${layers.capital !== false ? ' is-on' : ' is-off'}`}
          aria-pressed={layers.capital !== false}
          onClick={() => toggle('capital')}
        >
          <span className="legend-dots" aria-hidden>
            <i style={{ background: colors.bull }} />
          </span>
          Capital
        </button>
        {model.assets.map((a) => (
          <button
            key={a.symbol}
            type="button"
            className={`legend-chip${layers[a.symbol] !== false ? ' is-on' : ' is-off'}${
              focusSymbol === a.symbol ? ' is-focus' : ''
            }`}
            aria-pressed={layers[a.symbol] !== false}
            onClick={() => toggle(a.symbol)}
          >
            <span className="legend-dots" aria-hidden>
              <i style={{ background: a.color }} />
            </span>
            {a.label}
          </button>
        ))}
        <span className="legend-hint">Afficher / masquer · focus à droite</span>
      </div>

      <div className="chart-host" ref={hostRef} />

      {tip.visible && tip.point && (
        <div
          className="chart-tip"
          style={{ transform: `translate(${tip.x}px, ${tip.y}px)` }}
          role="tooltip"
        >
          <header>
            <strong>{fmtWhen(tip.point.time)}</strong>
            <span className={tip.point.vsInitial >= 0 ? 'up' : 'down'}>
              {signedEur(tip.point.vsInitial)}
            </span>
          </header>
          <div className="tip-section">
            <h4>Capital</h4>
            <dl>
              <div>
                <dt>Valeur</dt>
                <dd className="mono">{eur(tip.point.equity)}</dd>
              </div>
            </dl>
          </div>
          {tip.point.assets.filter((a) => a.invested > 0).length > 0 && (
            <div className="tip-section">
              <h4>Investi</h4>
              <dl>
                {tip.point.assets
                  .filter((a) => a.invested > 0)
                  .slice(0, 6)
                  .map((a) => (
                    <div key={a.symbol}>
                      <dt>
                        <i style={{ background: a.color }} /> {a.label}
                      </dt>
                      <dd className="mono">{eur(a.invested)}</dd>
                    </div>
                  ))}
              </dl>
            </div>
          )}
          {tip.point.events.length > 0 && (
            <div className="tip-section">
              <h4>À ce moment</h4>
              <ul className="portfolio-tip-trades">
                {tip.point.events.slice(0, 4).map((o) => {
                  const open = o.reason === 'open'
                  const dir = directionWords(o.side === 'BUY' ? 'LONG' : 'SHORT')
                  return (
                    <li key={o.id}>
                      <div className="portfolio-tip-trade-head">
                        <strong style={{ color: colorForSymbol(o.symbol) }}>
                          {assetName(o.symbol)}
                        </strong>
                        <span className={open ? 'up' : 'down'}>
                          {open ? dir.title : 'Clôture'}
                        </span>
                      </div>
                      <div className="portfolio-tip-trade-body">
                        Prix {price(o.filled_price)} · {eur(o.notional)}
                      </div>
                      <div className="portfolio-tip-trade-why muted">{acquisitionWhy(o)}</div>
                    </li>
                  )
                })}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
