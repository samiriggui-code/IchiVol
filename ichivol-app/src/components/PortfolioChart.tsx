import { useEffect, useMemo, useRef, useState } from 'react'
import {
  CandlestickSeries,
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
import { readChartColors } from '../lib/chartColors'
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
  '#2563eb', '#db2777', '#ea580c', '#7c3aed', '#0891b2',
  '#ca8a04', '#16a34a', '#e11d48', '#4f46e5', '#0d9488',
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

type CandleBar = {
  time: UTCTimestamp
  open: number
  high: number
  low: number
  close: number
}

type AssetRow = {
  symbol: string
  label: string
  color: string
  invested: number
  opens: PaperOrderRow[]
  line: { time: UTCTimestamp; value: number }[]
}

type Hover = {
  time: number
  open: number
  high: number
  low: number
  close: number
  vsInitial: number
  events: PaperOrderRow[]
  assetInvested: number | null
}

function resampleEquity(
  points: { time: number; equity: number }[],
  bucketSec: number,
  initial: number,
): CandleBar[] {
  if (points.length === 0) return []
  const buckets = new Map<number, number[]>()
  for (const p of points) {
    const key = Math.floor(p.time / bucketSec) * bucketSec
    const arr = buckets.get(key)
    if (arr) arr.push(p.equity)
    else buckets.set(key, [p.equity])
  }
  const keys = [...buckets.keys()].sort((a, b) => a - b)
  let prevClose = initial
  return keys.map((key) => {
    const vals = buckets.get(key)!
    const open = prevClose
    const close = vals[vals.length - 1]
    const high = Math.max(open, ...vals)
    const low = Math.min(open, ...vals)
    prevClose = close
    return {
      time: key as UTCTimestamp,
      open,
      high,
      low,
      close,
    }
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

function buildOpenMarkers(asset: AssetRow | null): SeriesMarker<Time>[] {
  if (!asset) return []
  const out: SeriesMarker<Time>[] = []
  for (const o of asset.opens) {
    const u = toUnix(o.time)
    if (u == null) continue
    out.push({
      time: u as UTCTimestamp,
      position: 'belowBar',
      color: asset.color,
      shape: 'circle',
      size: 1.4,
    })
  }
  return out
}

type LayerKey = 'candles' | 'asset' | 'orders'

/**
 * Graphe portefeuille calqué sur Marché :
 * bougies capital + timeframe + panneau latéral actions (contextes séparés).
 */
export function PortfolioChart({
  points,
  initial,
  orders = [],
  positions = [],
}: {
  points: Point[]
  initial: number
  orders?: PaperOrderRow[]
  positions?: PaperOverviewPosition[]
}) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const hostRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candleRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const assetRef = useRef<ISeriesApi<'Line'> | null>(null)
  const markersApiRef = useRef<ReturnType<typeof createSeriesMarkers<Time>> | null>(null)
  const hoverMap = useRef<Map<number, Hover>>(new Map())
  const layersRef = useRef<Record<LayerKey, boolean>>({
    candles: true,
    asset: true,
    orders: true,
  })

  const [range, setRange] = useState<PortfolioRange>('1d')
  const [focus, setFocus] = useState<'capital' | string>('capital')
  const [sideOpen, setSideOpen] = useState(true)
  const [layers, setLayers] = useState(layersRef.current)
  const [tip, setTip] = useState<{ visible: boolean; x: number; y: number; point: Hover | null }>({
    visible: false,
    x: 0,
    y: 0,
    point: null,
  })

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
    const candles = resampleEquity(equityRaw, bucket, initial)

    const sortedOrders = [...orders].sort((a, b) => Date.parse(a.time) - Date.parse(b.time))
    const bySym = new Map<string, { invested: number; steps: { t: number; v: number }[]; opens: PaperOrderRow[] }>()

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

    const times = candles.map((c) => Number(c.time))
    const assets: AssetRow[] = [...bySym.entries()]
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
    for (let i = 0; i < candles.length; i++) {
      const c = candles[i]
      const t = Number(c.time)
      map.set(t, {
        time: t,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
        vsInitial: c.close - initial,
        events: [],
        assetInvested: null,
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
      if (best != null && bestD <= bucket * 1.5) {
        map.get(best)!.events.push(o)
      }
    }

    return {
      candles,
      assets,
      map,
      last: candles.length ? candles[candles.length - 1].close : initial,
    }
  }, [points, initial, orders, positions, range])

  const focusedAsset = focus === 'capital' ? null : model.assets.find((a) => a.symbol === focus) ?? null

  useEffect(() => {
    layersRef.current = layers
    candleRef.current?.applyOptions({ visible: layers.candles })
    assetRef.current?.applyOptions({ visible: layers.asset && focusedAsset != null })
    markersApiRef.current?.setMarkers(
      layers.orders && focusedAsset ? buildOpenMarkers(focusedAsset) : [],
    )
  }, [layers, focusedAsset])

  useEffect(() => {
    const el = hostRef.current
    if (!el || model.candles.length < 2) return

    const colors = readChartColors()
    const chart = createChart(el, {
      width: el.clientWidth || 800,
      height: el.clientHeight || 420,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: colors.muted || '#888',
      },
      grid: {
        vertLines: { color: 'rgba(128,128,128,0.08)' },
        horzLines: { color: 'rgba(128,128,128,0.12)' },
      },
      crosshair: { mode: 0 },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false },
    })

    const candles = chart.addSeries(CandlestickSeries, {
      upColor: colors.bull,
      downColor: colors.bear,
      wickUpColor: colors.bull,
      wickDownColor: colors.bear,
      borderVisible: false,
      lastValueVisible: true,
      priceLineVisible: false,
    })
    candles.setData(model.candles)
    candles.createPriceLine({
      price: initial,
      color: colors.muted || '#888',
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: true,
      title: 'Départ',
    })

    const assetLine = chart.addSeries(LineSeries, {
      color: focusedAsset?.color ?? colors.tenkan,
      lineWidth: 2,
      lastValueVisible: true,
      priceLineVisible: false,
      crosshairMarkerVisible: true,
      visible: Boolean(focusedAsset) && layersRef.current.asset,
      title: focusedAsset?.label ?? 'Action',
    })
    if (focusedAsset && focusedAsset.line.length >= 2) {
      assetLine.setData(focusedAsset.line)
    }

    const markersApi = createSeriesMarkers(candles, [])
    chartRef.current = chart
    candleRef.current = candles
    assetRef.current = assetLine
    markersApiRef.current = markersApi
    hoverMap.current = model.map

    // seed markers for current focus
    if (layersRef.current.orders && focusedAsset) {
      markersApi.setMarkers(buildOpenMarkers(focusedAsset))
    }

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
        if (best != null) point = hoverMap.current.get(best) ?? null
      }
      if (!point) {
        setTip((prev) => (prev.visible ? { ...prev, visible: false, point: null } : prev))
        return
      }
      const assetInv =
        focusedAsset != null
          ? focusedAsset.line.find((p) => Number(p.time) === point!.time)?.value ??
            focusedAsset.line.reduce((acc, p) => (Number(p.time) <= point!.time ? p.value : acc), 0)
          : null
      const enriched = { ...point, assetInvested: assetInv }

      const wrap = wrapRef.current
      const tipW = 280
      const tipH = 260
      let x = param.point.x + 16
      let y = param.point.y + 16
      if (x + tipW > wrap.clientWidth - 8) x = param.point.x - tipW - 12
      if (y + tipH > wrap.clientHeight - 8) y = Math.max(8, param.point.y - tipH - 8)
      setTip({ visible: true, x: Math.max(8, x), y: Math.max(8, y), point: enriched })
    }
    chart.subscribeCrosshairMove(onMove)

    const ro = new ResizeObserver(() => {
      if (!hostRef.current) return
      chart.applyOptions({
        width: hostRef.current.clientWidth,
        height: hostRef.current.clientHeight,
      })
    })
    ro.observe(el)

    const onTheme = () => {
      const next = readChartColors()
      chart.applyOptions({ layout: { textColor: next.muted || '#888' } })
      candles.applyOptions({
        upColor: next.bull,
        downColor: next.bear,
        wickUpColor: next.bull,
        wickDownColor: next.bear,
      })
    }
    window.addEventListener(THEME_CHANGE_EVENT, onTheme)
    chart.timeScale().fitContent()

    return () => {
      ro.disconnect()
      window.removeEventListener(THEME_CHANGE_EVENT, onTheme)
      markersApi.setMarkers([])
      chart.remove()
      chartRef.current = null
      candleRef.current = null
      assetRef.current = null
      markersApiRef.current = null
    }
    // recreate when range/candles change; asset focus updates via separate effect when possible
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [model.candles, initial, range])

  // Update asset overlay without full remount when focus changes
  useEffect(() => {
    const line = assetRef.current
    if (!line) return
    if (!focusedAsset || focusedAsset.line.length < 2) {
      line.applyOptions({ visible: false })
      line.setData([])
      return
    }
    line.applyOptions({
      visible: layers.asset,
      color: focusedAsset.color,
      title: focusedAsset.label,
    })
    line.setData(focusedAsset.line)
  }, [focusedAsset, layers.asset])

  const up = model.last >= initial
  const colors = readChartColors()

  if (model.candles.length < 2) {
    return (
      <p className="muted broker-curve-empty">
        Pas assez d’historique encore — les bougies du capital apparaîtront après quelques cycles.
      </p>
    )
  }

  return (
    <div className={`portfolio-market${sideOpen ? '' : ' is-side-collapsed'}`}>
      <section className="chart-panel panel portfolio-chart-panel">
        <header className="panel-head">
          <h2>
            <span className="market-pair-title">
              {focusedAsset ? `${focusedAsset.label} · investi` : 'Capital du compte'}
            </span>
            <span className="market-pair-meta">
              {focusedAsset
                ? `${focusedAsset.symbol} · courbe argent placé`
                : `portefeuille · bougies · ${range}`}
            </span>
          </h2>
          <div className="panel-head-actions">
            <span className={`panel-meta ${up ? 'up' : 'down'}`}>
              {eur(model.last)} · {signedEur(model.last - initial)}
            </span>
            <button
              type="button"
              className="side-toggle"
              aria-expanded={sideOpen}
              aria-controls="portfolio-side"
              title={sideOpen ? 'Réduire le panneau' : 'Afficher le panneau'}
              onClick={() => setSideOpen((o) => !o)}
            >
              {sideOpen ? '⟩' : '⟨'}
            </button>
          </div>
        </header>

        <div className="chart-wrap" ref={wrapRef}>
          <div className="chart-legend" role="toolbar" aria-label="Couches">
            <button
              type="button"
              className={`legend-chip${layers.candles ? ' is-on' : ' is-off'}`}
              onClick={() => setLayers((p) => ({ ...p, candles: !p.candles }))}
            >
              <span className="legend-dots" aria-hidden>
                <i style={{ background: colors.bull }} />
                <i style={{ background: colors.bear }} />
              </span>
              Bougies capital
            </button>
            <button
              type="button"
              className={`legend-chip${layers.asset ? ' is-on' : ' is-off'}`}
              disabled={!focusedAsset}
              onClick={() => setLayers((p) => ({ ...p, asset: !p.asset }))}
            >
              <span className="legend-dots" aria-hidden>
                <i style={{ background: focusedAsset?.color ?? 'var(--muted)' }} />
              </span>
              Courbe action
            </button>
            <button
              type="button"
              className={`legend-chip${layers.orders ? ' is-on' : ' is-off'}`}
              disabled={!focusedAsset}
              onClick={() => setLayers((p) => ({ ...p, orders: !p.orders }))}
            >
              Achats
            </button>
            <span className="legend-hint">Comme Marché — clique pour afficher / masquer</span>
          </div>

          <div className="chart-host portfolio-chart-host" ref={hostRef} />

          {tip.visible && tip.point && (
            <div
              className="chart-tip"
              style={{ transform: `translate(${tip.x}px, ${tip.y}px)` }}
              role="tooltip"
            >
              <header>
                <strong>{fmtWhen(tip.point.time)}</strong>
                <span className={tip.point.close >= tip.point.open ? 'up' : 'down'}>
                  {tip.point.close >= tip.point.open ? 'hausse' : 'baisse'}
                </span>
              </header>
              <div className="tip-section">
                <h4>Capital (bougie)</h4>
                <dl>
                  <div>
                    <dt>O</dt>
                    <dd className="mono">{eur(tip.point.open)}</dd>
                  </div>
                  <div>
                    <dt>H</dt>
                    <dd className="mono">{eur(tip.point.high)}</dd>
                  </div>
                  <div>
                    <dt>L</dt>
                    <dd className="mono">{eur(tip.point.low)}</dd>
                  </div>
                  <div>
                    <dt>C</dt>
                    <dd className={`mono ${tip.point.close >= tip.point.open ? 'up' : 'down'}`}>
                      {eur(tip.point.close)}
                    </dd>
                  </div>
                  <div>
                    <dt>vs départ</dt>
                    <dd className={tip.point.vsInitial >= 0 ? 'up' : 'down'}>
                      {signedEur(tip.point.vsInitial)}
                    </dd>
                  </div>
                </dl>
              </div>
              {focusedAsset && tip.point.assetInvested != null && (
                <div className="tip-section">
                  <h4 style={{ color: focusedAsset.color }}>{focusedAsset.label} placé</h4>
                  <dl>
                    <div>
                      <dt>Investi</dt>
                      <dd className="mono">{eur(tip.point.assetInvested)}</dd>
                    </div>
                  </dl>
                </div>
              )}
              {tip.point.events.length > 0 && (
                <div className="tip-section">
                  <h4>Acquisitions / sorties</h4>
                  <ul className="portfolio-tip-trades">
                    {tip.point.events
                      .filter((o) => !focusedAsset || o.symbol === focusedAsset.symbol)
                      .slice(0, 4)
                      .map((o) => {
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

        <div className="tf-group tf-group--chart" role="group" aria-label="Chronologie">
          {PORTFOLIO_RANGES.map((tf) => (
            <button
              key={tf.id}
              type="button"
              className={tf.id === range ? 'is-active' : undefined}
              onClick={() => setRange(tf.id)}
            >
              {tf.label}
            </button>
          ))}
        </div>
      </section>

      <aside
        id="portfolio-side"
        className="side portfolio-side"
        hidden={!sideOpen}
        aria-hidden={!sideOpen}
      >
        <div className="panel">
          <header className="panel-head">
            <h2>Contextes</h2>
            <span className="panel-meta">capital ou une action</span>
          </header>
          <button
            type="button"
            className={`portfolio-side-item${focus === 'capital' ? ' is-active' : ''}`}
            onClick={() => setFocus('capital')}
          >
            <span className="portfolio-live-dot" style={{ background: 'var(--bull)' }} />
            <div className="portfolio-side-copy">
              <strong>Capital global</strong>
              <span className="muted">bougies du portefeuille</span>
            </div>
            <span className={`mono ${up ? 'up' : 'down'}`}>{eur(model.last)}</span>
          </button>
          <p className="subhead" style={{ padding: '0.5rem 0.75rem 0.2rem' }}>
            Actions acquises
          </p>
          {model.assets.length === 0 && (
            <p className="muted" style={{ padding: '0.4rem 0.75rem' }}>
              Aucune action encore.
            </p>
          )}
          {model.assets.map((a) => (
            <button
              key={a.symbol}
              type="button"
              className={`portfolio-side-item${focus === a.symbol ? ' is-active' : ''}`}
              onClick={() => setFocus(a.symbol)}
            >
              <span className="portfolio-live-dot" style={{ background: a.color }} />
              <div className="portfolio-side-copy">
                <strong>{a.label}</strong>
                <span className="muted">
                  {a.invested > 0 ? 'position ouverte' : 'plus ouvert · historique'}
                </span>
              </div>
              <span className="mono">{a.invested > 0 ? eur(a.invested) : '—'}</span>
            </button>
          ))}
        </div>
      </aside>
    </div>
  )
}
