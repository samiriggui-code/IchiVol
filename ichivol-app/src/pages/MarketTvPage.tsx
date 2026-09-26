/**
 * Marché TV — fenêtre plein écran hors DashboardShell.
 * Même données moteur que Marché (univers, OHLCV, watchlist multi-classe).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { MarketLayersMenu } from '../components/MarketLayersMenu'
import { PriceChart } from '../components/PriceChart'
import { fetchTickers24h } from '../lib/binance'
import { getScreener, type ScreenerDecisionRow } from '../lib/decisions'
import {
  OBJECT_LAYER_META,
  countObjectsByLayer,
  loadLayerPrefs,
  saveLayerPrefs,
  withIchimoku,
  type LayerPrefs,
} from '../lib/marketPrefs'
import type { Candle, Interval } from '../lib/types'
import {
  CLASS_LABELS,
  getEngineOhlcv,
  getEngineUniverse,
  type EngineAssetClass,
  type EngineInstrument,
} from '../lib/universe'
import { getChartObjects, type ChartObject } from '../lib/chartObjects'
import {
  fmtPctMaq,
  fmtPriceMaq,
  fmtRvolMaq,
  nearestSrObjects,
  shortSymbol,
} from './market/marketMaquetteHelpers'
import './MarketTvPage.css'

const TFS: { id: Interval; label: string }[] = [
  { id: '15m', label: '15M' },
  { id: '1h', label: '1H' },
  { id: '4h', label: '4H' },
  { id: '1d', label: '1D' },
]

type WatchRow = {
  id: string
  label: string
  price: number | null
  change24h: number | null
  rvol: number | null
}

export function MarketTvPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [instruments, setInstruments] = useState<EngineInstrument[]>([])
  const [assetClass, setAssetClass] = useState<EngineAssetClass | 'all'>('all')
  const [screenerRows, setScreenerRows] = useState<ScreenerDecisionRow[]>([])
  const [tickers24h, setTickers24h] = useState<Map<string, { price: number; change24h: number }>>(
    () => new Map(),
  )
  const [symbol, setSymbol] = useState(() => searchParams.get('symbol') || 'BTCUSDT')
  const [interval, setInterval] = useState<Interval>(() => {
    const iq = searchParams.get('interval')
    if (iq === '15m' || iq === '1h' || iq === '4h' || iq === '1d') return iq
    return '1h'
  })
  const [candles, setCandles] = useState<Candle[]>([])
  const [provider, setProvider] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [chartLoading, setChartLoading] = useState(false)
  const [layerPrefs, setLayerPrefs] = useState<LayerPrefs>(() => loadLayerPrefs())
  const [engineObjects, setEngineObjects] = useState<ChartObject[]>([])
  const [rvol, setRvol] = useState<number | null>(null)
  const [layersOpen, setLayersOpen] = useState(false)
  const layersAnchorRef = useRef<HTMLDivElement>(null)

  const ichimokuOn =
    layerPrefs.tenkan && layerPrefs.kijun && layerPrefs.spanA && layerPrefs.spanB
  const levelsOn = layerPrefs.structure

  const setLayers = useCallback((next: LayerPrefs) => {
    setLayerPrefs(next)
    saveLayerPrefs(next)
  }, [])

  const layerCounts = useMemo(() => countObjectsByLayer(engineObjects), [engineObjects])
  const activeObjectLayerCount = useMemo(
    () => OBJECT_LAYER_META.filter((m) => layerPrefs[m.key]).length,
    [layerPrefs],
  )

  useEffect(() => {
    if (!layersOpen) return
    const onDoc = (e: MouseEvent) => {
      const el = layersAnchorRef.current
      if (el && e.target instanceof Node && !el.contains(e.target)) setLayersOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setLayersOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDoc)
      document.removeEventListener('keydown', onKey)
    }
  }, [layersOpen])

  // Sync URL (bookmark / refresh TV)
  useEffect(() => {
    const next = new URLSearchParams()
    next.set('symbol', symbol)
    next.set('interval', interval)
    setSearchParams(next, { replace: true })
  }, [symbol, interval, setSearchParams])

  useEffect(() => {
    document.title = `${shortSymbol(symbol)} · TV Marché · IchiVol`
    return () => {
      document.title = 'IchiVol'
    }
  }, [symbol])

  useEffect(() => {
    let cancelled = false
    getEngineUniverse()
      .then((u) => {
        if (cancelled) return
        const wired = u.instruments.filter((i) => i.wired && i.enabled)
        setInstruments(wired)
        if (!wired.some((i) => i.id === symbol)) {
          const btc = wired.find((i) => i.id === 'BTCUSDT')
          const first = wired.find((i) => i.asset_class === 'crypto') ?? wired[0]
          if (btc) setSymbol(btc.id)
          else if (first) setSymbol(first.id)
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Univers indisponible')
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    let cancelled = false
    getScreener(interval, false)
      .then((res) => {
        if (!cancelled) setScreenerRows(res.rows)
      })
      .catch(() => {
        if (!cancelled) setScreenerRows([])
      })
    return () => {
      cancelled = true
    }
  }, [interval])

  useEffect(() => {
    let cancelled = false
    fetchTickers24h()
      .then((rows) => {
        if (cancelled) return
        const m = new Map<string, { price: number; change24h: number }>()
        for (const t of rows) {
          m.set(t.symbol, { price: t.lastPrice, change24h: t.priceChangePercent })
        }
        setTickers24h(m)
      })
      .catch(() => {
        if (!cancelled) setTickers24h(new Map())
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!symbol) return
    let cancelled = false
    setChartLoading(true)
    setError(null)
    getEngineOhlcv(symbol, interval, 300)
      .then((res) => {
        if (cancelled) return
        setCandles(res.candles)
        setProvider(res.provider)
      })
      .catch((e: unknown) => {
        if (cancelled) return
        setCandles([])
        setProvider(null)
        setError(e instanceof Error ? e.message : 'OHLCV indisponible')
      })
      .finally(() => {
        if (!cancelled) setChartLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [symbol, interval])

  useEffect(() => {
    if (!symbol) return
    let cancelled = false
    setEngineObjects([])
    getChartObjects(symbol, interval, 300, ['engine', 'user', 'claude'])
      .then((objs) => {
        if (!cancelled) setEngineObjects(objs)
      })
      .catch(() => {
        if (!cancelled) setEngineObjects([])
      })
    return () => {
      cancelled = true
    }
  }, [symbol, interval])

  const screenerById = useMemo(() => {
    const m = new Map<string, ScreenerDecisionRow>()
    for (const r of screenerRows) m.set(r.symbol, r)
    return m
  }, [screenerRows])

  useEffect(() => {
    setRvol(screenerById.get(symbol)?.rvol ?? null)
  }, [screenerById, symbol])

  const chartObjectsForView = useMemo(() => {
    const nearest = layerPrefs.structure
      ? nearestSrObjects(
          engineObjects,
          candles.length ? candles[candles.length - 1]!.close : null,
          symbol,
          interval,
        )
      : []
    return [...engineObjects, ...nearest]
  }, [engineObjects, candles, symbol, interval, layerPrefs.structure])

  const current = useMemo(
    () => instruments.find((i) => i.id === symbol) ?? null,
    [instruments, symbol],
  )

  const classOptions = useMemo(() => {
    const present = new Set(instruments.map((i) => i.asset_class))
    return (Object.keys(CLASS_LABELS) as EngineAssetClass[]).filter((c) => present.has(c))
  }, [instruments])

  const watchRows: WatchRow[] = useMemo(() => {
    const list =
      instruments.length > 0
        ? instruments
            .filter((i) => assetClass === 'all' || i.asset_class === assetClass)
            .slice(0, 80)
        : []
    return list.map((inst) => {
      const row = screenerById.get(inst.id)
      const tick = tickers24h.get(inst.id)
      const price =
        tick?.price && tick.price > 0
          ? tick.price
          : row?.price && row.price > 0
            ? row.price
            : null
      return {
        id: inst.id,
        label: shortSymbol(inst.id),
        price,
        change24h: tick != null && Number.isFinite(tick.change24h) ? tick.change24h : null,
        rvol: row?.rvol ?? null,
      }
    })
  }, [instruments, screenerById, tickers24h, assetClass])

  const selectedTick = tickers24h.get(symbol)
  const change24h =
    selectedTick != null && Number.isFinite(selectedTick.change24h)
      ? selectedTick.change24h
      : null
  const lastClose = candles.length ? candles[candles.length - 1]!.close : null
  const priceDisplay =
    (selectedTick?.price && selectedTick.price > 0 ? selectedTick.price : null) ??
    (screenerById.get(symbol)?.price && screenerById.get(symbol)!.price > 0
      ? screenerById.get(symbol)!.price
      : null) ??
    lastClose

  const quote = current?.quote ? ` / ${current.quote}` : ''
  const sourceLabel =
    provider === 'binance'
      ? 'Binance'
      : provider === 'twelve_data'
        ? 'Twelve Data'
        : provider
          ? provider
          : '—'

  return (
    <div className="market-tv">
      <header className="market-tv-bar">
        <div className="market-tv-brand">
          <span className="market-tv-mark">IchiVol</span>
          <span className="market-tv-mode">TV Marché</span>
        </div>
        <div className="market-tv-symbol">
          <h1>
            {shortSymbol(symbol)}
            <span>{quote}</span>
          </h1>
          <small>
            {sourceLabel} · bougies clôturées
            {chartLoading ? ' · chargement…' : ''}
          </small>
        </div>
        <div className="market-tv-stats" aria-label="Résumé">
          <span>
            PRIX <b>{fmtPriceMaq(priceDisplay)}</b>
          </span>
          <span>
            24H{' '}
            <b className={change24h == null ? undefined : change24h >= 0 ? 'up' : 'down'}>
              {fmtPctMaq(change24h)}
            </b>
          </span>
          <span>
            RVOL <b>{fmtRvolMaq(rvol)}</b>
          </span>
        </div>
        <div className="segmented" role="group" aria-label="Timeframe">
          {TFS.map((t) => (
            <button
              key={t.id}
              type="button"
              className={interval === t.id ? 'active' : undefined}
              onClick={() => setInterval(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="market-tv-actions">
          <Link className="market-tv-link" to={`/app/market?symbol=${encodeURIComponent(symbol)}`}>
            Page Marché
          </Link>
          <button type="button" className="market-tv-close" onClick={() => window.close()}>
            Fermer
          </button>
        </div>
      </header>

      {error && (
        <div className="market-tv-notice" role="alert">
          <span>△</span>
          <span>{error}</span>
        </div>
      )}

      <div className="market-tv-chips" role="tablist" aria-label="Classe d’actifs">
        <button
          type="button"
          className={assetClass === 'all' ? 'active' : undefined}
          onClick={() => setAssetClass('all')}
        >
          Tous
        </button>
        {classOptions.map((c) => (
          <button
            key={c}
            type="button"
            className={assetClass === c ? 'active' : undefined}
            onClick={() => setAssetClass(c)}
          >
            {CLASS_LABELS[c]}
          </button>
        ))}
      </div>

      <div className="market-tv-body">
        <aside className="market-tv-watch" aria-label="Multi-marché">
          {watchRows.length === 0 && (
            <button type="button" disabled>
              <b>—</b>
              <small>Chargement…</small>
            </button>
          )}
          {watchRows.map((w) => {
            const ch = w.change24h
            const up = ch != null && ch >= 0
            return (
              <button
                key={w.id}
                type="button"
                className={w.id === symbol ? 'active' : undefined}
                onClick={() => setSymbol(w.id)}
              >
                <b>{w.label}</b>
                <span className={ch == null ? 'chg-na' : up ? 'up' : 'down'}>{fmtPctMaq(ch)}</span>
                <small>{fmtPriceMaq(w.price)}</small>
              </button>
            )
          })}
        </aside>

        <section className="market-tv-chart" aria-label="Graphique">
          <div className="market-tv-chart-slot">
            {candles.length > 0 ? (
              <PriceChart
                candles={candles}
                symbol={symbol}
                timeframe={interval}
                layerPrefs={layerPrefs}
                onLayerPrefsChange={setLayers}
                chartObjects={chartObjectsForView}
              />
            ) : (
              <div className="market-tv-empty">Aucune bougie</div>
            )}
          </div>
          <div className="market-tv-tools">
            <label>
              <input
                type="checkbox"
                checked={ichimokuOn}
                onChange={(e) => setLayers(withIchimoku(layerPrefs, e.target.checked))}
              />{' '}
              Ichimoku 9 / 26 / 52
            </label>
            <label>
              <input
                type="checkbox"
                checked={levelsOn}
                onChange={(e) => setLayers({ ...layerPrefs, structure: e.target.checked })}
              />{' '}
              Supports / résistances
            </label>
            <div className="mkt-layers-anchor" ref={layersAnchorRef}>
              <button
                type="button"
                className={`mkt-layers-btn${layersOpen ? ' is-open' : ''}`}
                aria-expanded={layersOpen}
                onClick={() => setLayersOpen((o) => !o)}
              >
                Calques{activeObjectLayerCount ? ` · ${activeObjectLayerCount}` : ''}
              </button>
              {layersOpen && (
                <MarketLayersMenu
                  open
                  onClose={() => setLayersOpen(false)}
                  prefs={layerPrefs}
                  onChange={setLayers}
                  counts={layerCounts}
                  variant="menu"
                />
              )}
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
