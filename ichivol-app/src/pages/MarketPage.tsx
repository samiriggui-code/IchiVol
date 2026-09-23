import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { BiasPanel } from '../components/BiasPanel'
import { PriceChart } from '../components/PriceChart'
import { Screener } from '../components/Screener'
import { INTERVALS } from '../lib/binance'
import {
  getDecisionDetail,
  getScreener,
  type DecisionDetail,
  type ScreenerDecisionRow,
} from '../lib/decisions'
import { pipelineFromDecisionDetail } from '../lib/decisionPipeline'
import { displaySymbol } from '../lib/markets'
import { getChartObjects, type ChartObject } from '../lib/chartObjects'
import { onChartObjectsChanged } from '../lib/chartObjectsEvents'
import { useMarketSnapshot } from '../lib/marketSnapshot'
import {
  CLASS_BLURBS,
  CLASS_LABELS,
  getEngineOhlcv,
  getEngineUniverse,
  type EngineAssetClass,
  type EngineInstrument,
} from '../lib/universe'
import {
  type Candle,
  type Interval,
  type ScreenerRow,
  type Signal,
} from '../lib/types'

const ENGINE_TIMEFRAMES = new Set<Interval>(['15m', '1h', '4h', '1d'])

const CLASS_ORDER: EngineAssetClass[] = [
  'crypto',
  'forex',
  'metal',
  'index',
  'equity',
  'energy',
]

function decisionToBias(d: ScreenerDecisionRow['decision']): ScreenerRow['bias'] {
  if (d === 'STRONG_BUY' || d === 'BUY') return 'bull'
  if (d === 'STRONG_SELL' || d === 'SELL') return 'bear'
  return 'neutral'
}

function friendlyDataError(raw: string): string {
  const lower = raw.toLowerCase()
  if (lower.includes('timeout') || lower.includes('aborted') || lower.includes('dépassé')) {
    return (
      'Timeout moteur (screener trop long). Avec des seuils Settings custom le cache est bypassé. ' +
      'Remets les défauts RVOL/ATR ou attends le scan live.'
    )
  }
  if (lower.includes('credit') || lower.includes('rate limit') || lower.includes('8 api')) {
    return (
      'Quota Twelve Data (≈8 crédits/min) dépassé. Attends ~1 minute. ' +
      'Sur Forex/Métaux/Actions : un seul instrument à la fois (pas de scan parallèle).'
    )
  }
  return raw
}

export function MarketPage() {
  const { setSnapshot } = useMarketSnapshot()
  const [searchParams] = useSearchParams()
  const [instruments, setInstruments] = useState<EngineInstrument[]>([])
  const [universeError, setUniverseError] = useState<string | null>(null)
  const [marketClass, setMarketClass] = useState<EngineAssetClass>('crypto')
  const [symbol, setSymbol] = useState('BTCUSDT')
  const [interval, setInterval] = useState<Interval>('1h')
  const [candles, setCandles] = useState<Candle[]>([])
  const [chartProvider, setChartProvider] = useState<string | null>(null)
  const [chartObjects, setChartObjects] = useState<ChartObject[] | null>(null)
  const [signals, setSignals] = useState<Signal[]>([])
  const [chartLive, setChartLive] = useState<{
    bias: 'bull' | 'bear' | 'neutral'
    rvol: number
  }>({ bias: 'neutral', rvol: 0 })
  const [rows, setRows] = useState<ScreenerRow[]>([])
  const [chartLoading, setChartLoading] = useState(false)
  const [scanLoading, setScanLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sideOpen, setSideOpen] = useState(true)

  const [engineDetail, setEngineDetail] = useState<DecisionDetail | null>(null)
  const [engineLoading, setEngineLoading] = useState(false)
  const [engineError, setEngineError] = useState<string | null>(null)

  const classInstruments = useMemo(
    () => instruments.filter((i) => i.asset_class === marketClass),
    [instruments, marketClass],
  )
  const wiredInClass = useMemo(
    () => classInstruments.filter((i) => i.wired),
    [classInstruments],
  )
  const current = useMemo(
    () => instruments.find((i) => i.id === symbol) ?? null,
    [instruments, symbol],
  )
  const engineOn = Boolean(current?.wired && ENGINE_TIMEFRAMES.has(interval))

  const visibleClasses = useMemo(() => {
    const present = new Set(instruments.map((i) => i.asset_class))
    return CLASS_ORDER.filter((c) => present.has(c))
  }, [instruments])

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 980px)')
    const apply = () => {
      if (mq.matches) setSideOpen(true)
    }
    apply()
    mq.addEventListener('change', apply)
    return () => mq.removeEventListener('change', apply)
  }, [])

  useEffect(() => {
    let cancelled = false
    getEngineUniverse()
      .then((u) => {
        if (cancelled) return
        setInstruments(u.instruments)
        setUniverseError(null)
        const fromUrl = searchParams.get('symbol')
        const intervalQ = searchParams.get('interval')
        if (
          intervalQ === '15m' ||
          intervalQ === '1h' ||
          intervalQ === '4h' ||
          intervalQ === '1d'
        ) {
          setInterval(intervalQ)
        }
        if (fromUrl && u.instruments.some((i) => i.id === fromUrl)) {
          const inst = u.instruments.find((i) => i.id === fromUrl)!
          setSymbol(fromUrl)
          setMarketClass(inst.asset_class)
          return
        }
        const firstCrypto = u.instruments.find((i) => i.asset_class === 'crypto' && i.wired)
        if (firstCrypto) setSymbol((s) => (u.instruments.some((i) => i.id === s) ? s : firstCrypto.id))
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setUniverseError(err instanceof Error ? err.message : 'Univers moteur indisponible')
        }
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- deep-link on first universe load
  }, [])

  const selectClass = useCallback(
    (next: EngineAssetClass) => {
      setMarketClass(next)
      const list = instruments.filter((i) => i.asset_class === next)
      const pick = list.find((i) => i.wired) ?? list[0]
      if (pick) setSymbol(pick.id)
    },
    [instruments],
  )

  const loadChart = useCallback(async (sym: string, tf: Interval) => {
    setChartLoading(true)
    setError(null)
    setSignals([])
    setChartLive({ bias: 'neutral', rvol: 0 })
    try {
      const res = await getEngineOhlcv(sym, tf, 300)
      setCandles(res.candles)
      setChartProvider(res.provider)
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Erreur chargement chart'
      setError(friendlyDataError(msg))
      setCandles([])
      setChartProvider(null)
    } finally {
      setChartLoading(false)
    }
  }, [])

  /** Screener moteur = un seul appel partagé qui couvre déjà crypto (binance)
   * ET forex/métal/index/énergie (biquote, gratuit) via default_watchlist()
   * côté moteur -- seul twelve_data (actions) reste en liste locale pour ne
   * pas cramer son quota (~7 crédits/min) sur un scan multi-symboles. */
  const runClassScan = useCallback(async (tf: Interval, list: EngineInstrument[]) => {
    const wired = list.filter((i) => i.wired)
    setScanLoading(true)
    setError(null)
    try {
      if (list[0]?.provider !== 'twelve_data') {
        const res = await getScreener(tf, false)
        const bySym = new Map(res.rows.map((r) => [r.symbol, r]))
        const scanned: ScreenerRow[] = wired.map((inst) => {
          const eng = bySym.get(inst.id)
          return {
            symbol: inst.id,
            price: eng?.price ?? 0,
            change24h: 0,
            quoteVolume: 0,
            bias: eng ? decisionToBias(eng.decision) : 'neutral',
            rvol: eng?.rvol ?? 0,
            signals: [],
            lastSignal: null,
            engineDecision: eng?.decision,
            engineConfidence: eng?.confidence,
            enginePipeline: eng?.pipeline,
          }
        })
        scanned.sort((a, b) => (b.engineConfidence ?? 0) - (a.engineConfidence ?? 0))
        setRows(scanned)
        return
      }

      // Pas d’appels Twelve Data en rafale — lignes placeholder, détail au clic.
      setRows(
        wired.map((inst) => ({
          symbol: inst.id,
          price: 0,
          change24h: 0,
          quoteVolume: 0,
          bias: 'neutral' as const,
          rvol: 0,
          signals: [],
          lastSignal: null,
        })),
      )
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Erreur screener'
      setError(friendlyDataError(msg))
      setRows([])
    } finally {
      setScanLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!current?.wired) {
      setCandles([])
      setChartProvider(null)
      setEngineDetail(null)
      setEngineError(
        current && !current.wired
          ? `provider_not_wired: ${current.id} (${current.asset_class})`
          : null,
      )
      setEngineLoading(false)
      return
    }
    if (!ENGINE_TIMEFRAMES.has(interval)) return

    let cancelled = false
    const isTwelve = current.provider === 'twelve_data'

    // Twelve Data: ONE request (decision + candles). Crypto: chart + decision can parallelize (Binance free).
    if (isTwelve) {
      setChartLoading(true)
      setEngineLoading(true)
      setError(null)
      setEngineError(null)
      getDecisionDetail(symbol, interval, false, true)
        .then((d) => {
          if (cancelled) return
          setEngineDetail(d)
          if (d.candles?.length) {
            setCandles(d.candles)
            setChartProvider(d.provider ?? 'twelve_data')
          }
        })
        .catch((err: unknown) => {
          if (cancelled) return
          const msg = err instanceof Error ? err.message : 'Erreur moteur'
          setEngineDetail(null)
          setEngineError(friendlyDataError(msg))
          setError(friendlyDataError(msg))
          setCandles([])
          setChartProvider(null)
        })
        .finally(() => {
          if (cancelled) return
          setChartLoading(false)
          setEngineLoading(false)
        })
      return () => {
        cancelled = true
      }
    }

    void loadChart(symbol, interval)

    setEngineLoading(true)
    setEngineError(null)
    getDecisionDetail(symbol, interval, true, false)
      .then((d) => {
        if (!cancelled) setEngineDetail(d)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setEngineDetail(null)
        const msg = err instanceof Error ? err.message : 'Erreur moteur'
        setEngineError(friendlyDataError(msg))
      })
      .finally(() => {
        if (!cancelled) setEngineLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [symbol, interval, current, loadChart])

  useEffect(() => {
    setChartObjects(null)
    // Twelve Data (actions) : budget de crédits serré, /chart-objects refetche les bougies.
    if (!current?.wired || current.provider === 'twelve_data' || !ENGINE_TIMEFRAMES.has(interval)) {
      return
    }
    let cancelled = false
    const load = () => {
      getChartObjects(symbol, interval, 300)
        .then((objs) => {
          if (!cancelled) setChartObjects(objs)
        })
        .catch(() => {
          // Overlay optionnel : le graphique reste utilisable sans.
        })
    }
    load()
    // T2b: Copilot draw_*/delete → refetch overlays without remounting the page.
    const off = onChartObjectsChanged(load)
    return () => {
      cancelled = true
      off()
    }
  }, [symbol, interval, current])

  useEffect(() => {
    if (!classInstruments.length) return
    void runClassScan(interval, classInstruments)
  }, [interval, marketClass, classInstruments, runClassScan])

  const live = useMemo(
    () => ({
      bias: chartLive.bias,
      rvol: chartLive.rvol,
      price: candles.length ? (candles[candles.length - 1]?.close ?? null) : null,
    }),
    [candles, chartLive],
  )

  const enginePipeline = useMemo(
    () => (engineDetail ? pipelineFromDecisionDetail(engineDetail) : null),
    [engineDetail],
  )

  useEffect(() => {
    setSnapshot({ symbol, interval, live, signals, rows })
    return () => setSnapshot(null)
  }, [symbol, interval, live, signals, rows, setSnapshot])

  const providerLabel =
    chartProvider === 'twelve_data'
      ? 'Twelve Data'
      : chartProvider === 'binance'
        ? 'Binance Vision'
        : chartProvider ?? '—'

  return (
    <div className="market-page">
      <header className="market-head">
        <div className="market-head-copy">
          <h1>Marché</h1>
          <p className="muted">{CLASS_BLURBS[marketClass]}</p>
        </div>
        <div className="market-class-tabs" role="tablist" aria-label="Classe d’actif">
          {visibleClasses.map((c) => (
            <button
              key={c}
              type="button"
              role="tab"
              aria-selected={c === marketClass}
              className={c === marketClass ? 'is-active' : undefined}
              onClick={() => selectClass(c)}
            >
              {CLASS_LABELS[c]}
            </button>
          ))}
        </div>
      </header>

      <div className="market-toolbar topbar">
        <div className="controls">
          <label>
            Instrument
            <select value={symbol} onChange={(e) => setSymbol(e.target.value)}>
              {classInstruments.map((p) => (
                <option key={p.id} value={p.id} disabled={!p.wired}>
                  {p.label}
                  {!p.wired ? ' · non câblé' : ` · ${p.provider ?? ''}`} · {p.id}
                </option>
              ))}
            </select>
          </label>

          <div className="tf-group tf-group--toolbar" role="group" aria-label="Timeframe">
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

          <button
            type="button"
            className="ghost"
            disabled={!wiredInClass.length || scanLoading}
            onClick={() => void runClassScan(interval, classInstruments)}
          >
            {scanLoading ? 'Scan…' : 'Rescan'}
          </button>
        </div>
      </div>

      {(error || universeError) && (
        <div className="banner error" role="alert">
          {error ?? universeError}
        </div>
      )}
      <div className="banner info market-feed-note" role="note">
        Données via le moteur IchiVol ({providerLabel}) — pas de compte broker. Plan Twelve Data
        gratuit ≈ 8 crédits/min : sur Forex/Métaux/Actions, charge un symbole à la fois (liste sans
        scan parallèle).
      </div>

      <main className={`layout${sideOpen ? '' : ' is-side-collapsed'}`}>
        <section className="chart-panel panel">
          <header className="panel-head">
            <h2>
              <span className="market-pair-title">{current?.label ?? displaySymbol(symbol)}</span>
              <span className="market-pair-meta">
                {symbol} · {interval} · {providerLabel}
                {engineOn ? ' · moteur ON' : current && !current.wired ? ' · non câblé' : ''}
              </span>
            </h2>
            <div className="panel-head-actions">
              <span className="panel-meta">
                {chartLoading ? 'chargement…' : `${candles.length} bougies`}
              </span>
              <button
                type="button"
                className="side-toggle"
                aria-expanded={sideOpen}
                aria-controls="side-panel"
                title={sideOpen ? 'Réduire le panneau' : 'Afficher le panneau'}
                onClick={() => setSideOpen((open) => !open)}
              >
                {sideOpen ? '⟩' : '⟨'}
              </button>
            </div>
          </header>
          <PriceChart
            candles={candles}
            symbol={symbol}
            timeframe={interval}
            onSignals={setSignals}
            onLive={setChartLive}
            chartObjects={chartObjects}
          />
          <div className="tf-group tf-group--chart" role="group" aria-label="Timeframe">
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
        </section>
        <aside id="side-panel" className="side" hidden={!sideOpen} aria-hidden={!sideOpen}>
          <BiasPanel
            symbol={current?.label ?? displaySymbol(symbol)}
            signals={signals}
            bias={live.bias}
            rvol={live.rvol}
            price={live.price}
            engineDetail={engineDetail}
            enginePipeline={enginePipeline}
            engineLoading={engineLoading}
            engineError={engineError}
            engineAvailable={engineOn}
          />
          <Screener
            rows={rows}
            loading={scanLoading}
            selected={symbol}
            onSelect={setSymbol}
            title={`Screener · ${CLASS_LABELS[marketClass]}`}
            showEngine={engineOn || marketClass === 'crypto'}
          />
        </aside>
      </main>
    </div>
  )
}
