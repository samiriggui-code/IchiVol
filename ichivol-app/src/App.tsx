import { useCallback, useEffect, useMemo, useState } from 'react'
import { BiasPanel } from './components/BiasPanel'
import { PriceChart } from './components/PriceChart'
import { Screener } from './components/Screener'
import {
  INTERVALS,
  WATCHLIST,
  fetchKlines,
  fetchTickers24h,
  mapPool,
} from './lib/binance'
import { computeIchimoku } from './lib/ichimoku'
import { biasFromIchi, computeVolumePulse } from './lib/signals'
import {
  DEFAULT_ICHI,
  DEFAULT_VOL,
  type Candle,
  type Interval,
  type ScreenerRow,
  type Signal,
} from './lib/types'

export default function App() {
  const [symbol, setSymbol] = useState('BTCUSDT')
  const [interval, setInterval] = useState<Interval>('1h')
  const [candles, setCandles] = useState<Candle[]>([])
  const [signals, setSignals] = useState<Signal[]>([])
  const [rows, setRows] = useState<ScreenerRow[]>([])
  const [chartLoading, setChartLoading] = useState(false)
  const [scanLoading, setScanLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadChart = useCallback(async (sym: string, tf: Interval) => {
    setChartLoading(true)
    setError(null)
    try {
      setCandles(await fetchKlines(sym, tf, 300))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur chargement chart')
      setCandles([])
    } finally {
      setChartLoading(false)
    }
  }, [])

  const runScreener = useCallback(async (tf: Interval) => {
    setScanLoading(true)
    try {
      const tickers = await fetchTickers24h()
      const bySym = new Map(tickers.map((t) => [t.symbol, t]))
      const universe = WATCHLIST.filter((s) => bySym.has(s))
      const scanned = await mapPool(universe, 4, async (sym) => {
        const kl = await fetchKlines(sym, tf, 200)
        const ichi = computeIchimoku(kl, DEFAULT_ICHI)
        const { volumes, signals: sigs } = computeVolumePulse(kl, DEFAULT_ICHI, DEFAULT_VOL)
        const last = ichi[ichi.length - 1]
        const lastVol = volumes[volumes.length - 1]
        const t = bySym.get(sym)!
        const row: ScreenerRow = {
          symbol: sym,
          price: t.lastPrice,
          change24h: t.priceChangePercent,
          quoteVolume: t.quoteVolume,
          bias: biasFromIchi(last?.aboveCloud ?? false, last?.belowCloud ?? false),
          rvol: lastVol?.rvol ?? 0,
          signals: sigs,
          lastSignal: sigs.length ? sigs[sigs.length - 1] : null,
        }
        return row
      })
      scanned.sort((a, b) => {
        const hit = (r: ScreenerRow) => (r.lastSignal ? 1 : 0)
        if (hit(a) !== hit(b)) return hit(b) - hit(a)
        return b.rvol - a.rvol
      })
      setRows(scanned)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur screener')
    } finally {
      setScanLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadChart(symbol, interval)
  }, [symbol, interval, loadChart])

  useEffect(() => {
    void runScreener(interval)
  }, [interval, runScreener])

  const live = useMemo(() => {
    if (!candles.length) return { bias: 'neutral' as const, rvol: 0, price: null as number | null }
    const ichi = computeIchimoku(candles, DEFAULT_ICHI)
    const { volumes } = computeVolumePulse(candles, DEFAULT_ICHI, DEFAULT_VOL)
    const last = ichi[ichi.length - 1]
    const lastVol = volumes[volumes.length - 1]
    return {
      bias: biasFromIchi(last.aboveCloud, last.belowCloud),
      rvol: lastVol?.rvol ?? 0,
      price: candles[candles.length - 1]?.close ?? null,
    }
  }, [candles])

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">IV</span>
          <div>
            <strong>IchiVol</strong>
            <p>Ichimoku × volume — signaux confirmés seulement</p>
          </div>
        </div>
        <div className="controls">
          <label>
            Paire
            <select value={symbol} onChange={(e) => setSymbol(e.target.value)}>
              {WATCHLIST.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </label>
          <div className="tf-group" role="group" aria-label="Timeframe">
            {INTERVALS.map((tf) => (
              <button
                key={tf.id}
                type="button"
                className={tf.id === interval ? 'is-active' : undefined}
                onClick={() => setInterval(tf.id)}
              >
                {tf.label}
              </button>
            ))}
          </div>
          <button type="button" className="ghost" onClick={() => void runScreener(interval)}>
            Rescan
          </button>
        </div>
      </header>

      {error && <div className="banner error">{error}</div>}

      <main className="layout">
        <section className="chart-panel panel">
          <header className="panel-head">
            <h2>{symbol} · {interval}</h2>
            <span className="panel-meta">
              {chartLoading ? 'chargement…' : `${candles.length} bougies`}
            </span>
          </header>
          <PriceChart candles={candles} onSignals={setSignals} />
        </section>
        <aside className="side">
          <BiasPanel
            symbol={symbol}
            signals={signals}
            bias={live.bias}
            rvol={live.rvol}
            price={live.price}
          />
          <Screener
            rows={rows}
            loading={scanLoading}
            selected={symbol}
            onSelect={setSymbol}
          />
        </aside>
      </main>
    </div>
  )
}
