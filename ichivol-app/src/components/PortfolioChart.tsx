import { useEffect, useMemo, useRef, useState } from 'react'
import {
  AreaSeries,
  ColorType,
  createChart,
  LineSeries,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type MouseEventParams,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts'
import { readChartColors, type ChartColors } from '../lib/chartColors'
import type { PaperOrderRow, PaperOverviewPosition } from '../lib/paper'
import { THEME_CHANGE_EVENT } from '../lib/theme'
import { assetName, eur, signedEur } from '../lib/tradeStory'

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

type AssetRow = {
  symbol: string
  label: string
  color: string
  line: { time: UTCTimestamp; value: number }[]
}

type Hover = {
  time: number
  equity: number
  vsInitial: number
  assets: { symbol: string; label: string; color: string; invested: number }[]
}

type LayerVis = Record<string, boolean>

/** Courbe valeur du portefeuille (€). Exposition engagée = couches optionnelles (off par défaut). */
export function PortfolioChart({
  points,
  initial,
  orders = [],
  positions = [],
  range,
}: {
  points: Point[]
  initial: number
  orders?: PaperOrderRow[]
  positions?: PaperOverviewPosition[]
  range: PortfolioRange
}) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const hostRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const capitalRef = useRef<ISeriesApi<'Area'> | null>(null)
  const assetSeriesRef = useRef<Map<string, ISeriesApi<'Line'>>>(new Map())
  const startLineDone = useRef(false)
  const hoverMap = useRef<Map<number, Hover>>(new Map())
  const layersRef = useRef<LayerVis>({ capital: true })
  const colorsRef = useRef<ChartColors>(readChartColors())

  const [colors, setColors] = useState<ChartColors>(() => readChartColors())
  /** Asset layers stay off until the user opts in (avoids dual-scale confusion). */
  const [layers, setLayers] = useState<LayerVis>({ capital: true })
  const [showExposure, setShowExposure] = useState(false)
  const [tip, setTip] = useState<{
    visible: boolean
    x: number
    y: number
    point: Hover | null
  }>({ visible: false, x: 0, y: 0, point: null })

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
    if (capital.length < 2 && equityRaw.length >= 2) {
      capital = equityRaw.map((p) => ({ time: p.time as UTCTimestamp, value: p.equity }))
    }

    const sortedOrders = [...orders].sort((a, b) => Date.parse(a.time) - Date.parse(b.time))
    const bySym = new Map<string, { invested: number; steps: { t: number; v: number }[] }>()

    for (const o of sortedOrders) {
      const u = toUnix(o.time)
      if (u == null) continue
      let row = bySym.get(o.symbol)
      if (!row) {
        row = { invested: 0, steps: [{ t: u - 1, v: 0 }] }
        bySym.set(o.symbol, row)
      }
      if (o.reason === 'open') {
        row.invested += Math.abs(o.notional || 0)
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
      })
    }

    const times = capital.map((p) => Number(p.time))
    const assets: AssetRow[] = [...bySym.entries()]
      .map(([symbol, row]) => ({
        symbol,
        label: assetName(symbol),
        color: colorForSymbol(symbol),
        line: times.map((t) => ({
          time: t as UTCTimestamp,
          value: sampleSteps(row.steps, t),
        })),
      }))
      .filter((a) => a.line.some((p) => p.value > 0))
      .sort((a, b) => a.label.localeCompare(b.label))

    const map = new Map<number, Hover>()
    for (const c of capital) {
      const t = Number(c.time)
      map.set(t, {
        time: t,
        equity: c.value,
        vsInitial: c.value - initial,
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

    return { capital, assets, map, nRaw: equityRaw.length }
  }, [points, initial, orders, positions, range])

  useEffect(() => {
    setLayers((prev) => {
      const next: LayerVis = { capital: prev.capital !== false }
      for (const a of model.assets) {
        // Keep prior explicit choice; default off so equity scale stays clean.
        next[a.symbol] = prev[a.symbol] === true
      }
      layersRef.current = next
      return next
    })
  }, [model.assets])

  useEffect(() => {
    const chart = chartRef.current
    if (!chart) return
    const anyAssetOn = showExposure && model.assets.some((a) => layers[a.symbol] === true)
    chart.applyOptions({
      leftPriceScale: { visible: anyAssetOn, borderVisible: false },
    })
  }, [showExposure, layers, model.assets])

  useEffect(() => {
    layersRef.current = layers
  }, [layers])

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
      leftPriceScale: { visible: false, borderVisible: false },
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
        vertLine: { color: `${initialColors.muted}55`, labelBackgroundColor: initialColors.background },
        horzLine: { color: `${initialColors.muted}55`, labelBackgroundColor: initialColors.background },
      },
    })

    const capital = chart.addSeries(AreaSeries, {
      lineWidth: 2,
      lineColor: initialColors.bull || '#16a34a',
      topColor: `${initialColors.bull || '#16a34a'}40`,
      bottomColor: `${initialColors.bull || '#16a34a'}05`,
      lastValueVisible: true,
      priceLineVisible: false,
      priceScaleId: 'right',
      title: 'Valeur (€)',
    })
    capital.priceScale().applyOptions({ scaleMargins: { top: 0.08, bottom: 0.12 } })

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
      const tipW = 220
      const tipH = 160
      let x = param.point.x + 14
      let y = param.point.y + 14
      if (x + tipW > wrap.clientWidth - 8) x = param.point.x - tipW - 10
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
        topColor: `${next.bull || '#16a34a'}40`,
        bottomColor: `${next.bull || '#16a34a'}05`,
      })
    }
    window.addEventListener(THEME_CHANGE_EVENT, onTheme)

    return () => {
      window.removeEventListener(THEME_CHANGE_EVENT, onTheme)
      chart.unsubscribeCrosshairMove(onMove)
      ro.disconnect()
      chart.remove()
      chartRef.current = null
      capitalRef.current = null
      assetSeriesRef.current.clear()
      startLineDone.current = false
    }
  }, [])

  useEffect(() => {
    const chart = chartRef.current
    const capital = capitalRef.current
    if (!chart || !capital) return

    if (model.capital.length < 2) {
      capital.setData([])
      for (const s of assetSeriesRef.current.values()) s.setData([])
      return
    }

    capital.setData(model.capital)
    capital.applyOptions({ visible: layersRef.current.capital !== false })
    if (!startLineDone.current) {
      capital.createPriceLine({
        price: initial,
        color: `${colorsRef.current.muted || '#888'}99`,
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: false,
        title: '',
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
          lineWidth: 2,
          lastValueVisible: false,
          priceLineVisible: false,
          crosshairMarkerVisible: false,
          priceScaleId: 'left',
          title: '',
        })
        series.priceScale().applyOptions({ scaleMargins: { top: 0.2, bottom: 0.05 } })
        assetSeriesRef.current.set(a.symbol, series)
      }
      series.applyOptions({
        visible: layersRef.current[a.symbol] === true,
        color: a.color,
      })
      series.setData(a.line)
    }

    chart.timeScale().fitContent()
  }, [model, initial])

  useEffect(() => {
    capitalRef.current?.applyOptions({ visible: layers.capital !== false })
    for (const [sym, series] of assetSeriesRef.current) {
      series.applyOptions({ visible: layers[sym] === true })
    }
  }, [layers])

  if (model.capital.length < 2) {
    return (
      <div className="chart-wrap">
        <p className="muted broker-curve-empty">
          Pas assez d’historique ({model.nRaw} pt{model.nRaw > 1 ? 's' : ''}).
        </p>
      </div>
    )
  }

  const toggle = (key: string) => {
    setLayers((prev) => {
      const on =
        key === 'capital' ? !(prev.capital !== false) : !(prev[key] === true)
      const next = { ...prev, [key]: on }
      layersRef.current = next
      return next
    })
  }

  const exposureOn = showExposure

  return (
    <div className="chart-wrap" ref={wrapRef}>
      <div className="chart-legend" role="toolbar" aria-label="Couches">
        <button
          type="button"
          className={`legend-chip${layers.capital !== false ? ' is-on' : ' is-off'}`}
          aria-pressed={layers.capital !== false}
          onClick={() => toggle('capital')}
        >
          <span className="legend-dots" aria-hidden>
            <i style={{ background: colors.bull }} />
          </span>
          Valeur (€)
        </button>
        <button
          type="button"
          className={`legend-chip${exposureOn ? ' is-on' : ' is-off'}`}
          aria-pressed={exposureOn}
          onClick={() => {
            setShowExposure((v) => {
              const next = !v
              if (next) {
                setLayers((prev) => {
                  const allOn: LayerVis = { ...prev, capital: prev.capital !== false }
                  for (const a of model.assets) allOn[a.symbol] = true
                  layersRef.current = allOn
                  return allOn
                })
              } else {
                setLayers((prev) => {
                  const allOff: LayerVis = { capital: prev.capital !== false }
                  for (const a of model.assets) allOff[a.symbol] = false
                  layersRef.current = allOff
                  return allOff
                })
              }
              return next
            })
          }}
        >
          Exposition engagée
        </button>
        {exposureOn &&
          model.assets.map((a) => (
            <button
              key={a.symbol}
              type="button"
              className={`legend-chip${layers[a.symbol] === true ? ' is-on' : ' is-off'}`}
              aria-pressed={layers[a.symbol] === true}
              onClick={() => toggle(a.symbol)}
            >
              <span className="legend-dots" aria-hidden>
                <i style={{ background: a.color }} />
              </span>
              {a.label}
            </button>
          ))}
      </div>

      <p className="muted chart-snapshot-note">
        Échelle droite = valeur totale du compte (€). Ligne pointillée = capital initial. Snapshots
        ≈ toutes les 5 min — pas de points inventés ; les longues lignes relient des absences de
        mesure. « Exposition engagée » (optionnel) = coût d’acquisition par actif, échelle gauche
        séparée.
      </p>

      <div className="chart-host" ref={hostRef} />

      {tip.visible && tip.point && (
        <div
          className="chart-tip chart-tip--slim"
          style={{ transform: `translate(${tip.x}px, ${tip.y}px)` }}
          role="tooltip"
        >
          <header>
            <strong>{fmtWhen(tip.point.time)}</strong>
            <span className={tip.point.vsInitial >= 0 ? 'up' : 'down'}>
              {signedEur(tip.point.vsInitial)}
            </span>
          </header>
          <dl>
            <div>
              <dt>Valeur</dt>
              <dd className="mono">{eur(tip.point.equity)}</dd>
            </div>
            {exposureOn &&
              tip.point.assets
                .filter((a) => a.invested > 0 && layers[a.symbol] === true)
                .slice(0, 4)
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
    </div>
  )
}
