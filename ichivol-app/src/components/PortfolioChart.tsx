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
  '#c026d3',
  '#65a30d',
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
    weekday: 'short',
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function acquisitionWhy(o: PaperOrderRow): string {
  if (o.reason === 'open') {
    return o.side === 'BUY'
      ? 'Ouverture longue — le moteur a jugé le signal assez fort pour entrer'
      : 'Ouverture short — pari à la baisse validé par le pipeline'
  }
  return exitReasonLabel(o.reason)
}

type SymbolSeries = {
  symbol: string
  label: string
  color: string
  /** Montant investi cumulé dans le temps (step). */
  line: { time: UTCTimestamp; value: number }[]
  /** Achats / ouvertures pour marqueurs + bulles. */
  opens: PaperOrderRow[]
  currentInvested: number
}

type Hover = {
  time: number
  equity: number
  vsInitial: number
  vsInitialPct: number
  bySymbol: { symbol: string; label: string; color: string; invested: number }[]
  events: PaperOrderRow[]
}

/**
 * Graphes organisés : capital global + une courbe par action acquise,
 * sélection indépendante, bulles d’acquisition détaillées (pas de fourre-tout).
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
  const capitalRef = useRef<ISeriesApi<'Area'> | null>(null)
  const symbolRefs = useRef<Map<string, ISeriesApi<'Line'>>>(new Map())
  const markersApiRef = useRef<ReturnType<typeof createSeriesMarkers<Time>> | null>(null)
  const hoverMap = useRef<Map<number, Hover>>(new Map())
  const visibleRef = useRef<{ capital: boolean; symbols: Set<string> }>({
    capital: true,
    symbols: new Set(),
  })

  const [showCapital, setShowCapital] = useState(true)
  const [selected, setSelected] = useState<Set<string>>(() => new Set())
  const [tip, setTip] = useState<{ visible: boolean; x: number; y: number; point: Hover | null }>({
    visible: false,
    x: 0,
    y: 0,
    point: null,
  })
  const initSelectDone = useRef(false)

  const model = useMemo(() => {
    const equityPts = points
      .map((p) => {
        const u = toUnix(p.t)
        if (u == null || !Number.isFinite(p.equity)) return null
        return { time: u as UTCTimestamp, equity: p.equity }
      })
      .filter((x): x is { time: UTCTimestamp; equity: number } => x != null)
      .sort((a, b) => Number(a.time) - Number(b.time))
      .filter((p, i, arr) => i === 0 || p.time !== arr[i - 1].time)

    const sortedOrders = [...orders].sort(
      (a, b) => Date.parse(a.time) - Date.parse(b.time),
    )

    // Courbes « argent placé » par symbole (escalier sur les ordres)
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
      const isOpen = o.reason === 'open'
      if (isOpen) {
        row.invested += Math.abs(o.notional || 0)
        row.opens.push(o)
      } else {
        row.invested = Math.max(0, row.invested - Math.abs(o.notional || 0))
      }
      row.steps.push({ t: u, v: row.invested })
    }

    // Enrichir avec positions ouvertes actuelles (si pas encore dans les ordres chargés)
    for (const p of positions) {
      if (p.status !== 'OPEN') continue
      if (!bySym.has(p.symbol)) {
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
    }

    const times =
      equityPts.length > 0
        ? equityPts.map((p) => Number(p.time))
        : [...bySym.values()].flatMap((r) => r.steps.map((s) => s.t)).sort((a, b) => a - b)

    function sampleSteps(steps: { t: number; v: number }[], t: number): number {
      let v = 0
      for (const s of steps) {
        if (s.t <= t) v = s.v
        else break
      }
      return v
    }

    const symbols: SymbolSeries[] = [...bySym.entries()]
      .map(([symbol, row]) => {
        const line = times.map((t) => ({
          time: t as UTCTimestamp,
          value: sampleSteps(row.steps, t),
        }))
        // compresser plateaux inutiles
        const compact: typeof line = []
        for (const pt of line) {
          const prev = compact[compact.length - 1]
          if (prev && prev.value === pt.value && compact.length > 1) {
            compact[compact.length - 1] = pt
          } else {
            compact.push(pt)
          }
        }
        return {
          symbol,
          label: assetName(symbol),
          color: colorForSymbol(symbol),
          line: compact.length >= 2 ? compact : line,
          opens: row.opens,
          currentInvested: row.invested,
        }
      })
      .filter((s) => s.line.some((p) => p.value > 0) || s.opens.length > 0)
      .sort((a, b) => b.currentInvested - a.currentInvested || a.label.localeCompare(b.label))

    const capital = equityPts.map((p) => ({ time: p.time, value: p.equity }))

    // Hover map sur les timestamps du capital (ou des symboles)
    const map = new Map<number, Hover>()
    const baseTimes =
      equityPts.length > 0 ? equityPts.map((p) => Number(p.time)) : times.slice(0, 200)

    for (const t of baseTimes) {
      const eq = equityPts.find((p) => Number(p.time) === t)?.equity ?? initial
      map.set(t, {
        time: t,
        equity: eq,
        vsInitial: eq - initial,
        vsInitialPct: initial ? (eq - initial) / initial : 0,
        bySymbol: symbols.map((s) => ({
          symbol: s.symbol,
          label: s.label,
          color: s.color,
          invested: sampleSteps(bySym.get(s.symbol)!.steps, t),
        })),
        events: [],
      })
    }

    // Rattacher ordres au point le plus proche (≤ 3h)
    for (const o of sortedOrders) {
      const u = toUnix(o.time)
      if (u == null || map.size === 0) continue
      let best: number | null = null
      let bestDist = Infinity
      for (const t of map.keys()) {
        const d = Math.abs(t - u)
        if (d < bestDist) {
          bestDist = d
          best = t
        }
      }
      if (best != null && bestDist <= 3 * 3600) {
        map.get(best)!.events.push(o)
      }
    }

    return {
      capital,
      symbols,
      map,
      lastEquity: equityPts.length ? equityPts[equityPts.length - 1].equity : initial,
      hasCapital: capital.length >= 2,
    }
  }, [points, initial, orders, positions])

  // Première sélection : capital + top 5 actions encore investies
  useEffect(() => {
    if (initSelectDone.current || model.symbols.length === 0) return
    initSelectDone.current = true
    const top = model.symbols
      .filter((s) => s.currentInvested > 0)
      .slice(0, 5)
      .map((s) => s.symbol)
    const fallback = model.symbols.slice(0, 3).map((s) => s.symbol)
    setSelected(new Set(top.length ? top : fallback))
  }, [model.symbols])

  visibleRef.current = { capital: showCapital, symbols: selected }

  useEffect(() => {
    const el = hostRef.current
    if (!el) return
    if (!model.hasCapital && model.symbols.length === 0) return

    const colors = readChartColors()
    const chart = createChart(el, {
      width: el.clientWidth || 800,
      height: 400,
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
        vertLine: { color: 'rgba(128,128,128,0.4)', width: 1, style: LineStyle.Dashed },
        horzLine: { color: 'rgba(128,128,128,0.4)', width: 1, style: LineStyle.Dashed },
      },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false },
    })

    const capital = chart.addSeries(AreaSeries, {
      lineWidth: 3,
      lineColor: colors.bull || '#16a34a',
      topColor: `${colors.bull || '#16a34a'}44`,
      bottomColor: `${colors.bull || '#16a34a'}05`,
      lastValueVisible: true,
      priceLineVisible: false,
      crosshairMarkerVisible: true,
      crosshairMarkerRadius: 6,
      title: 'Capital',
      visible: visibleRef.current.capital,
    })
    if (model.hasCapital) {
      capital.setData(model.capital)
      capital.createPriceLine({
        price: initial,
        color: colors.muted || '#888',
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: 'Départ',
      })
    }

    const symMap = new Map<string, ISeriesApi<'Line'>>()
    for (const s of model.symbols) {
      const series = chart.addSeries(LineSeries, {
        color: s.color,
        lineWidth: 2,
        lastValueVisible: true,
        priceLineVisible: false,
        crosshairMarkerVisible: true,
        crosshairMarkerRadius: 5,
        title: s.label,
        visible: visibleRef.current.symbols.has(s.symbol),
      })
      if (s.line.length >= 2) series.setData(s.line)
      symMap.set(s.symbol, series)
    }

    // Marqueurs uniquement pour les symboles sélectionnés — sans texte (évite le fourre-tout)
    const markerHost = capital
    const markersApi = createSeriesMarkers(markerHost, [])
    function refreshMarkers() {
      const markers: SeriesMarker<Time>[] = []
      for (const s of model.symbols) {
        if (!visibleRef.current.symbols.has(s.symbol)) continue
        for (const o of s.opens) {
          const u = toUnix(o.time)
          if (u == null) continue
          markers.push({
            time: u as UTCTimestamp,
            position: 'belowBar',
            color: s.color,
            shape: 'circle',
            size: 1.2,
          })
        }
      }
      markersApi.setMarkers(markers)
    }
    refreshMarkers()

    chartRef.current = chart
    capitalRef.current = capital
    symbolRefs.current = symMap
    markersApiRef.current = markersApi
    hoverMap.current = model.map
    ;(el as HTMLElement & { __refreshMarkers?: () => void }).__refreshMarkers = refreshMarkers

    const onMove = (param: MouseEventParams<Time>) => {
      if (!param.point || param.point.x < 0 || param.point.y < 0 || !param.time || !wrapRef.current) {
        setTip((prev) => (prev.visible ? { ...prev, visible: false, point: null } : prev))
        return
      }
      const t =
        typeof param.time === 'number'
          ? param.time
          : typeof param.time === 'string'
            ? Math.floor(Date.parse(param.time) / 1000)
            : null
      if (t == null) {
        setTip((prev) => (prev.visible ? { ...prev, visible: false, point: null } : prev))
        return
      }
      // point exact ou voisin le plus proche
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
        if (best != null && bestD <= 24 * 3600) point = hoverMap.current.get(best) ?? null
      }
      if (!point) {
        setTip((prev) => (prev.visible ? { ...prev, visible: false, point: null } : prev))
        return
      }
      const wrap = wrapRef.current
      const tipW = 300
      const tipH = 280
      let x = param.point.x + 18
      let y = param.point.y + 14
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
      capital.applyOptions({
        lineColor: next.bull || '#16a34a',
        topColor: `${next.bull || '#16a34a'}44`,
        bottomColor: `${next.bull || '#16a34a'}05`,
      })
    }
    window.addEventListener(THEME_CHANGE_EVENT, onTheme)
    chart.timeScale().fitContent()

    return () => {
      window.removeEventListener('resize', onResize)
      window.removeEventListener(THEME_CHANGE_EVENT, onTheme)
      markersApi.setMarkers([])
      chart.remove()
      chartRef.current = null
      capitalRef.current = null
      symbolRefs.current = new Map()
      markersApiRef.current = null
    }
  }, [model, initial])

  // Sync visibilité sans recreer le chart
  useEffect(() => {
    visibleRef.current = { capital: showCapital, symbols: selected }
    capitalRef.current?.applyOptions({ visible: showCapital && model.hasCapital })
    for (const [sym, series] of symbolRefs.current) {
      series.applyOptions({ visible: selected.has(sym) })
    }
    const el = hostRef.current as (HTMLElement & { __refreshMarkers?: () => void }) | null
    el?.__refreshMarkers?.()
  }, [showCapital, selected, model.hasCapital])

  function toggleSymbol(sym: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(sym)) next.delete(sym)
      else next.add(sym)
      return next
    })
  }

  function selectAll() {
    setShowCapital(true)
    setSelected(new Set(model.symbols.map((s) => s.symbol)))
  }

  function selectNone() {
    setShowCapital(false)
    setSelected(new Set())
  }

  function onlyCapital() {
    setShowCapital(true)
    setSelected(new Set())
  }

  if (!model.hasCapital && model.symbols.length === 0) {
    return (
      <p className="muted broker-curve-empty">
        Pas encore assez d’historique — le graphe apparaîtra après les premiers trades.
      </p>
    )
  }

  const openNow = model.symbols.filter((s) => s.currentInvested > 0)

  return (
    <div className="portfolio-chart" ref={wrapRef}>
      <div className="portfolio-chart-head">
        <div className="portfolio-curve-picks" role="toolbar" aria-label="Courbes affichées">
          <span className="portfolio-curve-picks-label">Courbes</span>
          <button type="button" className="ghost portfolio-mini" onClick={selectAll}>
            Tout
          </button>
          <button type="button" className="ghost portfolio-mini" onClick={onlyCapital}>
            Capital seul
          </button>
          <button type="button" className="ghost portfolio-mini" onClick={selectNone}>
            Rien
          </button>
          <button
            type="button"
            className={`legend-chip${showCapital ? ' is-on' : ' is-off'}`}
            onClick={() => setShowCapital((v) => !v)}
            disabled={!model.hasCapital}
          >
            <span className="legend-dots" aria-hidden>
              <i style={{ background: 'var(--bull)' }} />
            </span>
            Capital global
          </button>
          {model.symbols.map((s) => (
            <button
              key={s.symbol}
              type="button"
              className={`legend-chip${selected.has(s.symbol) ? ' is-on' : ' is-off'}`}
              onClick={() => toggleSymbol(s.symbol)}
              title={
                s.currentInvested > 0
                  ? `Investi maintenant : ${eur(s.currentInvested)}`
                  : 'Plus de position ouverte'
              }
            >
              <span className="legend-dots" aria-hidden>
                <i style={{ background: s.color }} />
              </span>
              {s.label}
              {s.currentInvested > 0 && (
                <span className="portfolio-chip-amt">{eur(s.currentInvested, 0)}</span>
              )}
            </button>
          ))}
        </div>
        {openNow.length > 0 && (
          <div className="portfolio-live-cards" aria-label="Actions détenues">
            {openNow.slice(0, 6).map((s) => (
              <button
                key={s.symbol}
                type="button"
                className={`portfolio-live-card${selected.has(s.symbol) ? ' is-on' : ''}`}
                style={{ borderColor: selected.has(s.symbol) ? s.color : undefined }}
                onClick={() => toggleSymbol(s.symbol)}
              >
                <span className="portfolio-live-dot" style={{ background: s.color }} />
                <strong>{s.label}</strong>
                <span>{eur(s.currentInvested)}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      <div ref={hostRef} className="portfolio-chart-host" />

      <p className="muted portfolio-chart-hint">
        Survolez une barre : détail du capital + acquisitions (prix, montant, pourquoi). Cliquez une
        couleur pour afficher / masquer la courbe. Les pastilles = achats des actions sélectionnées
        (sans labels qui se marchent dessus).
      </p>

      {tip.visible && tip.point && (
        <aside className="chart-tip portfolio-tip" style={{ left: tip.x, top: tip.y }} aria-hidden>
          <header>
            <strong>{fmtWhen(tip.point.time)}</strong>
            <span className={tip.point.vsInitial >= 0 ? 'up' : 'down'}>
              {signedEur(tip.point.vsInitial)}
            </span>
          </header>
          <div className="tip-section">
            <h4>Capital du compte</h4>
            <dl>
              <div>
                <dt>Valeur</dt>
                <dd>{eur(tip.point.equity)}</dd>
              </div>
              <div>
                <dt>vs départ ({eur(initial, 0)})</dt>
                <dd className={tip.point.vsInitial >= 0 ? 'up' : 'down'}>
                  {(tip.point.vsInitialPct * 100).toFixed(2)} %
                </dd>
              </div>
            </dl>
          </div>
          {tip.point.bySymbol.some((s) => s.invested > 0 && selected.has(s.symbol)) && (
            <div className="tip-section">
              <h4>Argent placé (courbes actives)</h4>
              <ul className="portfolio-tip-symbols">
                {tip.point.bySymbol
                  .filter((s) => s.invested > 0 && selected.has(s.symbol))
                  .map((s) => (
                    <li key={s.symbol}>
                      <i style={{ background: s.color }} />
                      <strong>{s.label}</strong>
                      <span>{eur(s.invested)}</span>
                    </li>
                  ))}
              </ul>
            </div>
          )}
          {tip.point.events.length > 0 && (
            <div className="tip-section">
              <h4>À ce moment</h4>
              <ul className="portfolio-tip-trades">
                {tip.point.events.slice(0, 5).map((o) => {
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
                        {o.qty ? ` · qty ${o.qty.toPrecision(4)}` : ''}
                      </div>
                      <div className="portfolio-tip-trade-why muted">{acquisitionWhy(o)}</div>
                    </li>
                  )
                })}
              </ul>
            </div>
          )}
        </aside>
      )}
    </div>
  )
}
