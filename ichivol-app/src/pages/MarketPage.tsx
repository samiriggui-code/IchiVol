import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { BiasPanel } from '../components/BiasPanel'
import { BacktestOverlaySheet } from '../components/BacktestOverlaySheet'
import { MarkTradeSheet, type MarkTradeStep } from '../components/MarkTradeSheet'
import { PriceChart, type ChartPickPoint } from '../components/PriceChart'
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
import {
  getChartObjects,
  postUserTradeSetup,
  type ChartObject,
  type UserTradePointType,
} from '../lib/chartObjects'
import { notifyChartObjectsChanged, onChartObjectsChanged } from '../lib/chartObjectsEvents'
import {
  postBacktestOverlay,
  type BacktestOutcomeFilter,
  type BacktestOverlayCounts,
  type BacktestOverlayTrade,
  type BacktestRejectedSignal,
} from '../lib/backtestOverlay'
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
const MARK_STEPS: UserTradePointType[] = ['entry', 'stop', 'target']

function newSetupId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `setup-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}

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

  // T2c — Marquer un trade (ENTRY → STOP → TARGET en mémoire, Valider = /setup)
  const [markOpen, setMarkOpen] = useState(false)
  const [markStep, setMarkStep] = useState<MarkTradeStep>('entry')
  const [markSetupId, setMarkSetupId] = useState<string | null>(null)
  const [markPlaced, setMarkPlaced] = useState<
    Partial<Record<'entry' | 'stop' | 'target', { price: number; time: number }>>
  >({})
  const [markSaving, setMarkSaving] = useState(false)
  const [markError, setMarkError] = useState<string | null>(null)

  // T4a — Backtest overlay (ephemeral BACKTEST objects layered on ENGINE/USER/CLAUDE)
  const [btSheetOpen, setBtSheetOpen] = useState(false)
  const [btRulesetId, setBtRulesetId] = useState<string | null>(null)
  const [btOutcome, setBtOutcome] = useState<BacktestOutcomeFilter>('all')
  const [btExitReason, setBtExitReason] = useState<string | null>(null)
  const [btDirection, setBtDirection] = useState<string | null>(null)
  const [btObjects, setBtObjects] = useState<ChartObject[]>([])
  const [btTrades, setBtTrades] = useState<BacktestOverlayTrade[]>([])
  const [btRejected, setBtRejected] = useState<BacktestRejectedSignal[]>([])
  const [btCounts, setBtCounts] = useState<BacktestOverlayCounts | null>(null)
  const [btActive, setBtActive] = useState(false)
  const [btLoading, setBtLoading] = useState(false)
  const [btError, setBtError] = useState<string | null>(null)

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
    // Chart-objects refetche OHLCV ; cache provider 90s + grounding moteur.
    // Twelve Data inclus (T2c revue Claude) — erreur claire à la validation.
    if (!current?.wired || !ENGINE_TIMEFRAMES.has(interval)) {
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

  const canMarkTrade =
    Boolean(current?.wired) && ENGINE_TIMEFRAMES.has(interval) && candles.length > 0

  const startMarkTrade = useCallback(() => {
    setMarkSetupId(newSetupId())
    setMarkStep('entry')
    setMarkPlaced({})
    setMarkError(null)
    setMarkSaving(false)
    setMarkOpen(true)
  }, [])

  const cancelMarkTrade = useCallback(() => {
    setMarkOpen(false)
    setMarkStep('entry')
    setMarkPlaced({})
    setMarkSetupId(null)
    setMarkError(null)
    setMarkSaving(false)
  }, [])

  const onPickPoint = useCallback(
    (point: ChartPickPoint) => {
      if (!markOpen || markSaving || markStep === 'review') return
      const step = markStep
      setMarkError(null)
      setMarkPlaced((prev) => ({ ...prev, [step]: point }))
      const idx = MARK_STEPS.indexOf(step)
      if (idx >= 0 && idx < MARK_STEPS.length - 1) {
        setMarkStep(MARK_STEPS[idx + 1]!)
      } else {
        setMarkStep('review')
      }
    },
    [markOpen, markSaving, markStep],
  )

  const validateMarkTrade = useCallback(async () => {
    if (!markSetupId || !markPlaced.entry || !markPlaced.stop || !markPlaced.target) return
    setMarkSaving(true)
    setMarkError(null)
    try {
      await postUserTradeSetup(symbol, {
        timeframe: interval,
        setup_id: markSetupId,
        entry: markPlaced.entry,
        stop: markPlaced.stop,
        target: markPlaced.target,
      })
      notifyChartObjectsChanged({ tool: 'user_setup', ok: true })
      cancelMarkTrade()
    } catch (err: unknown) {
      setMarkError(err instanceof Error ? err.message : 'Échec validation')
    } finally {
      setMarkSaving(false)
    }
  }, [markSetupId, markPlaced, symbol, interval, cancelMarkTrade])

  // Reset mark mode + backtest overlay when symbol / TF changes.
  useEffect(() => {
    if (markOpen) cancelMarkTrade()
    setBtObjects([])
    setBtTrades([])
    setBtRejected([])
    setBtCounts(null)
    setBtActive(false)
    setBtError(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol, interval])

  const clearBacktestOverlay = useCallback(() => {
    setBtObjects([])
    setBtTrades([])
    setBtRejected([])
    setBtCounts(null)
    setBtActive(false)
    setBtError(null)
  }, [])

  const loadBacktestOverlay = useCallback(
    async (
      outcome: BacktestOutcomeFilter = btOutcome,
      exitReason: string | null = btExitReason,
      direction: string | null = btDirection,
    ) => {
      if (!btRulesetId) return
      setBtLoading(true)
      setBtError(null)
      try {
        const res = await postBacktestOverlay({
          symbol,
          timeframe: interval,
          limit: 300,
          ruleset_id: btRulesetId,
          outcome,
          exit_reason: exitReason,
          direction,
          include_rejected: true,
        })
        setBtObjects(res.objects)
        setBtTrades(res.trades)
        setBtRejected(res.rejected ?? [])
        setBtCounts(res.counts)
        setBtActive(true)
      } catch (err: unknown) {
        setBtError(err instanceof Error ? err.message : 'Échec backtest')
      } finally {
        setBtLoading(false)
      }
    },
    [btRulesetId, btOutcome, btExitReason, btDirection, symbol, interval],
  )

  const onBtOutcome = useCallback(
    (o: BacktestOutcomeFilter) => {
      setBtOutcome(o)
      if (btActive) void loadBacktestOverlay(o, btExitReason, btDirection)
    },
    [btActive, btExitReason, btDirection, loadBacktestOverlay],
  )

  const onBtExitReason = useCallback(
    (v: string | null) => {
      setBtExitReason(v)
      if (btActive) void loadBacktestOverlay(btOutcome, v, btDirection)
    },
    [btActive, btOutcome, btDirection, loadBacktestOverlay],
  )

  const onBtDirection = useCallback(
    (v: string | null) => {
      setBtDirection(v)
      if (btActive) void loadBacktestOverlay(btOutcome, btExitReason, v)
    },
    [btActive, btOutcome, btExitReason, loadBacktestOverlay],
  )

  const mergedChartObjects = useMemo(() => {
    const base = chartObjects ?? []
    if (!btObjects.length) return chartObjects
    return [...base, ...btObjects]
  }, [chartObjects, btObjects])

  return (
    <div
      className={`market-page${markOpen ? ' is-mark-trade' : ''}${btSheetOpen ? ' is-backtest-overlay' : ''}`}
    >
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
                className={markOpen ? 'is-active' : 'ghost'}
                disabled={!canMarkTrade || markSaving}
                title={
                  canMarkTrade
                    ? 'Poser ENTRY / STOP / TARGET sur le graphique'
                    : 'Disponible sur symboles câblés (TF moteur)'
                }
                onClick={() => (markOpen ? cancelMarkTrade() : startMarkTrade())}
              >
                {markOpen ? 'Annuler marquage' : 'Marquer un trade'}
              </button>
              <button
                type="button"
                className={btSheetOpen || btActive ? 'is-active' : 'ghost'}
                disabled={!canMarkTrade || btLoading}
                title="Afficher les trades d’une stratégie catalogue sur le chart"
                onClick={() => setBtSheetOpen((o) => !o)}
              >
                Backtest
              </button>
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
            chartObjects={mergedChartObjects}
            pickMode={markOpen && markStep !== 'review'}
            onPickPoint={onPickPoint}
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

      {markOpen ? (
        <MarkTradeSheet
          symbolLabel={current?.label ?? displaySymbol(symbol)}
          step={markStep}
          saving={markSaving}
          error={markError}
          placed={markPlaced}
          onCancel={cancelMarkTrade}
          onValidate={() => void validateMarkTrade()}
        />
      ) : null}

      {btSheetOpen ? (
        <BacktestOverlaySheet
          symbolLabel={current?.label ?? displaySymbol(symbol)}
          selectedRulesetId={btRulesetId}
          outcome={btOutcome}
          counts={btCounts}
          trades={btTrades}
          rejected={btRejected}
          exitReason={btExitReason}
          direction={btDirection}
          loading={btLoading}
          error={btError}
          active={btActive}
          onSelectRuleset={setBtRulesetId}
          onOutcome={onBtOutcome}
          onExitReason={onBtExitReason}
          onDirection={onBtDirection}
          onShow={() => void loadBacktestOverlay(btOutcome)}
          onClear={clearBacktestOverlay}
          onClose={() => setBtSheetOpen(false)}
        />
      ) : null}
    </div>
  )
}
