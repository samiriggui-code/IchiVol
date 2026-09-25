import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from 'react'
import { useSearchParams } from 'react-router-dom'
import type { MarkTradeStep } from '../../components/MarkTradeSheet'
import { buildContextBadges } from '../../components/MarketWatchlist'
import type { ChartPickPoint } from '../../components/PriceChart'
import type { BacktestUiFilter } from '../../components/BacktestOverlaySheet'
import {
  getDecisionDetail,
  getScreener,
  type DecisionDetail,
} from '../../lib/decisions'
import { pipelineFromDecisionDetail } from '../../lib/decisionPipeline'
import {
  listUserDecisions,
  type UserDecisionRow,
} from '../../lib/userDecisions'
import {
  getChartObjects,
  postUserTradeSetup,
  type ChartObject,
} from '../../lib/chartObjects'
import { notifyChartObjectsChanged, onChartObjectsChanged } from '../../lib/chartObjectsEvents'
import {
  postBacktestOverlay,
  type BacktestOutcomeFilter,
  type BacktestOverlayCounts,
  type BacktestOverlayTrade,
  type BacktestRejectedSignal,
} from '../../lib/backtestOverlay'
import type { BacktestMetrics } from '../../lib/backtest'
import { useMarketSnapshot } from '../../lib/marketSnapshot'
import { listWatchlist } from '../../lib/watchlist'
import {
  OBJECT_LAYER_META,
  countObjectsByLayer,
  loadLayerPrefs,
  loadLayoutPrefs,
  saveLayerPrefs,
  saveLayoutPrefs,
  type IndicatorLayerKey,
  type LayerPrefs,
  type MarketLayoutPrefs,
  type WatchlistSortKey,
} from '../../lib/marketPrefs'
import {
  getEngineOhlcv,
  getEngineUniverse,
  type EngineAssetClass,
  type EngineInstrument,
} from '../../lib/universe'
import {
  type Candle,
  type Interval,
  type ScreenerRow,
  type Signal,
} from '../../lib/types'
import {
  ENGINE_TIMEFRAMES,
  MARK_STEPS,
  change24hFromCandles,
  decisionToBias,
  friendlyDataError,
  isAssetClass,
  newSetupId,
} from './marketHelpers'

export function useMarketController() {
  const { setSnapshot } = useMarketSnapshot()
  const [searchParams] = useSearchParams()
  const pinnedOnly = searchParams.get('filter') === 'pinned'
  const [pinnedSymbols, setPinnedSymbols] = useState<Set<string> | null>(null)
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

  const [layout, setLayout] = useState<MarketLayoutPrefs>(() => loadLayoutPrefs())
  const [layerPrefs, setLayerPrefs] = useState<LayerPrefs>(() => loadLayerPrefs())
  const [isMobile, setIsMobile] = useState(false)

  const [searchOpen, setSearchOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [layersOpen, setLayersOpen] = useState(false)
  const [indicatorsOpen, setIndicatorsOpen] = useState(false)
  const [infoOpen, setInfoOpen] = useState(false)

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
  const [btRulesetId, setBtRulesetId] = useState<string | null>(null)
  const [btOutcome, setBtOutcome] = useState<BacktestOutcomeFilter>('all')
  const [btUiFilter, setBtUiFilter] = useState<BacktestUiFilter>('all')
  const [btExitReason, setBtExitReason] = useState<string | null>(null)
  const [btDirection, setBtDirection] = useState<string | null>(null)
  const [btRegimeLabel, setBtRegimeLabel] = useState<string | null>(null)
  const [btObjects, setBtObjects] = useState<ChartObject[]>([])
  const [btTrades, setBtTrades] = useState<BacktestOverlayTrade[]>([])
  const [btRejected, setBtRejected] = useState<BacktestRejectedSignal[]>([])
  const [btCounts, setBtCounts] = useState<BacktestOverlayCounts | null>(null)
  const [btMetrics, setBtMetrics] = useState<BacktestMetrics | null>(null)
  const [btActive, setBtActive] = useState(false)
  const [btLoading, setBtLoading] = useState(false)
  const [btError, setBtError] = useState<string | null>(null)

  const [journalRows, setJournalRows] = useState<UserDecisionRow[]>([])
  const [journalLoading, setJournalLoading] = useState(false)
  const [journalError, setJournalError] = useState<string | null>(null)

  const resizeRef = useRef<{ startX: number; startW: number } | null>(null)
  const indicatorsRef = useRef<HTMLDivElement | null>(null)
  const infoRef = useRef<HTMLDivElement | null>(null)

  const classFilter = isAssetClass(layout.classFilter) ? layout.classFilter : null

  const allWired = useMemo(() => instruments.filter((i) => i.wired), [instruments])
  const current = useMemo(
    () => instruments.find((i) => i.id === symbol) ?? null,
    [instruments, symbol],
  )
  const engineOn = Boolean(current?.wired && ENGINE_TIMEFRAMES.has(interval))
  const activeObjectLayerCount = useMemo(
    () => OBJECT_LAYER_META.filter((m) => layerPrefs[m.key]).length,
    [layerPrefs],
  )

  const updateLayout = useCallback((patch: Partial<MarketLayoutPrefs>) => {
    setLayout((prev) => {
      const next = { ...prev, ...patch }
      saveLayoutPrefs(next)
      return next
    })
  }, [])

  const setLayerPrefsAndSave = useCallback((next: LayerPrefs) => {
    setLayerPrefs(next)
    saveLayerPrefs(next)
  }, [])

  const selectSymbol = useCallback(
    (next: string) => {
      setSymbol(next)
      const inst = instruments.find((i) => i.id === next)
      if (inst) setMarketClass(inst.asset_class)
      setSearchOpen(false)
      setSearchQuery('')
    },
    [instruments],
  )

  const onClassFilter = useCallback(
    (c: EngineAssetClass | null) => {
      updateLayout({ classFilter: c })
    },
    [updateLayout],
  )

  const onSort = useCallback(
    (key: WatchlistSortKey) => {
      if (layout.sortKey === key) {
        updateLayout({ sortDir: layout.sortDir === 'asc' ? 'desc' : 'asc' })
      } else {
        updateLayout({ sortKey: key, sortDir: key === 'symbol' ? 'asc' : 'desc' })
      }
    },
    [layout.sortKey, layout.sortDir, updateLayout],
  )

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 980px)')
    const apply = () => setIsMobile(mq.matches)
    apply()
    mq.addEventListener('change', apply)
    return () => mq.removeEventListener('change', apply)
  }, [])

  useEffect(() => {
    if (!pinnedOnly) {
      setPinnedSymbols(null)
      return
    }
    let cancelled = false
    listWatchlist()
      .then((rows) => {
        if (!cancelled) setPinnedSymbols(new Set(rows.map((r) => r.symbol)))
      })
      .catch(() => {
        if (!cancelled) setPinnedSymbols(new Set())
      })
    return () => {
      cancelled = true
    }
  }, [pinnedOnly])

  useEffect(() => {
    if (!indicatorsOpen && !infoOpen) return
    const onDoc = (e: MouseEvent) => {
      const t = e.target as Node
      if (indicatorsOpen && indicatorsRef.current && !indicatorsRef.current.contains(t)) {
        setIndicatorsOpen(false)
      }
      if (infoOpen && infoRef.current && !infoRef.current.contains(t)) {
        setInfoOpen(false)
      }
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIndicatorsOpen(false)
        setInfoOpen(false)
        setLayersOpen(false)
        if (!isMobile) setSearchOpen(false)
      }
    }
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDoc)
      document.removeEventListener('keydown', onKey)
    }
  }, [indicatorsOpen, infoOpen, isMobile])

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
   * pas cramer son quota (~7 crédits/min) sur un scan multi-symboles.
   * Watchlist UI-MARKET : scanne TOUS les instruments câblés (toutes classes). */
  const runClassScan = useCallback(async (tf: Interval, list: EngineInstrument[]) => {
    const wired = list.filter((i) => i.wired)
    setScanLoading(true)
    setError(null)
    try {
      const allTwelve =
        wired.length > 0 && wired.every((i) => i.provider === 'twelve_data')

      if (!allTwelve) {
        const res = await getScreener(tf, false)
        const bySym = new Map(res.rows.map((r) => [r.symbol, r]))
        const scanned: ScreenerRow[] = wired.map((inst) => {
          const eng = bySym.get(inst.id)
          const row: ScreenerRow = {
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
            labContext: eng?.lab_context,
          }
          return {     setSignals,
    setChartLive,
    btRulesetId,
    setBtRulesetId,
    runClassScan,
    marketClass,
    scanLoading,
...row, context: buildContextBadges(row) }
        })
        scanned.sort((a, b) => (b.engineConfidence ?? 0) - (a.engineConfidence ?? 0))
        setRows(scanned)
        return
      }

      // Pas d’appels Twelve Data en rafale — lignes placeholder, détail au clic.
      setRows(
        wired.map((inst) => {
          const row: ScreenerRow = {
            symbol: inst.id,
            price: 0,
            change24h: 0,
            quoteVolume: 0,
            bias: 'neutral' as const,
            rvol: 0,
            signals: [],
            lastSignal: null,
          }
          return { ...row, context: buildContextBadges(row) }
        }),
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
    if (!instruments.length) return
    void runClassScan(interval, instruments)
  }, [interval, instruments, runClassScan])

  const live = useMemo(
    () => ({
      bias: chartLive.bias,
      rvol: chartLive.rvol,
      price: candles.length ? (candles[candles.length - 1]?.close ?? null) : null,
    }),
    [candles, chartLive],
  )

  /** Top-bar / bandeau % — dérivé des bougies (~24h), jamais inventé. */
  const change24hDisplay = useMemo(() => change24hFromCandles(candles), [candles])

  /** RVOL : moteur d’abord, sinon chart live — absent → null (« — »). */
  const summaryRvol = useMemo((): number | null => {
    if (engineDetail?.rvol != null && Number.isFinite(engineDetail.rvol)) {
      return engineDetail.rvol
    }
    if (candles.length > 0 && Number.isFinite(chartLive.rvol)) {
      return chartLive.rvol
    }
    return null
  }, [engineDetail, candles.length, chartLive.rvol])

  const enginePipeline = useMemo(
    () => (engineDetail ? pipelineFromDecisionDetail(engineDetail) : null),
    [engineDetail],
  )

  const journalForSymbol = useMemo(
    () => journalRows.filter((r) => r.symbol === symbol),
    [journalRows, symbol],
  )

  useEffect(() => {
    if (isMobile || !layout.bottomOpen || layout.bottomTab !== 'journal') return
    let cancelled = false
    setJournalLoading(true)
    setJournalError(null)
    listUserDecisions(80)
      .then((rows) => {
        if (!cancelled) setJournalRows(rows)
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setJournalError(err instanceof Error ? err.message : 'Journal indisponible')
          setJournalRows([])
        }
      })
      .finally(() => {
        if (!cancelled) setJournalLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [isMobile, layout.bottomOpen, layout.bottomTab, symbol])

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

  const isTwelveData = chartProvider === 'twelve_data' || current?.provider === 'twelve_data'

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
    setBtMetrics(null)
    setBtActive(false)
    setBtError(null)
    setBtUiFilter('all')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol, interval])

  const clearBacktestOverlay = useCallback(() => {
    setBtObjects([])
    setBtTrades([])
    setBtRejected([])
    setBtCounts(null)
    setBtMetrics(null)
    setBtActive(false)
    setBtError(null)
    setBtUiFilter('all')
  }, [])

  const loadBacktestOverlay = useCallback(
    async (
      outcome: BacktestOutcomeFilter = btOutcome,
      exitReason: string | null = btExitReason,
      direction: string | null = btDirection,
      regimeLabel: string | null = btRegimeLabel,
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
          regime_label: regimeLabel,
          include_rejected: true,
        })
        setBtObjects(res.objects)
        setBtTrades(res.trades)
        setBtRejected(res.rejected ?? [])
        setBtCounts(res.counts)
        setBtMetrics(res.metrics ?? null)
        setBtActive(true)
      } catch (err: unknown) {
        setBtError(err instanceof Error ? err.message : 'Échec backtest')
      } finally {
        setBtLoading(false)
      }
    },
    [btRulesetId, btOutcome, btExitReason, btDirection, btRegimeLabel, symbol, interval],
  )

  const onBtOutcome = useCallback(
    (o: BacktestOutcomeFilter) => {
      setBtOutcome(o)
      setBtUiFilter(o)
      if (btActive) void loadBacktestOverlay(o, btExitReason, btDirection, btRegimeLabel)
    },
    [btActive, btExitReason, btDirection, btRegimeLabel, loadBacktestOverlay],
  )

  const onBtUiFilter = useCallback(
    (f: BacktestUiFilter) => {
      setBtUiFilter(f)
      if (f === 'rejected') return
      setBtOutcome(f)
      if (btActive) void loadBacktestOverlay(f, btExitReason, btDirection, btRegimeLabel)
    },
    [btActive, btExitReason, btDirection, btRegimeLabel, loadBacktestOverlay],
  )

  const onBtExitReason = useCallback(
    (v: string | null) => {
      setBtExitReason(v)
      if (btActive) void loadBacktestOverlay(btOutcome, v, btDirection, btRegimeLabel)
    },
    [btActive, btOutcome, btDirection, btRegimeLabel, loadBacktestOverlay],
  )

  const onBtDirection = useCallback(
    (v: string | null) => {
      setBtDirection(v)
      if (btActive) void loadBacktestOverlay(btOutcome, btExitReason, v, btRegimeLabel)
    },
    [btActive, btOutcome, btExitReason, btRegimeLabel, loadBacktestOverlay],
  )

  const onBtRegimeLabel = useCallback(
    (v: string | null) => {
      setBtRegimeLabel(v)
      if (btActive) void loadBacktestOverlay(btOutcome, btExitReason, btDirection, v)
    },
    [btActive, btOutcome, btExitReason, btDirection, loadBacktestOverlay],
  )

  const mergedChartObjects = useMemo(() => {
    const base = chartObjects ?? []
    if (!btObjects.length) return chartObjects
    return [...base, ...btObjects]
  }, [chartObjects, btObjects])

  const layerCounts = useMemo(
    () => countObjectsByLayer(mergedChartObjects),
    [mergedChartObjects],
  )

  const btPanelOpen =
    (!isMobile && layout.bottomOpen && layout.bottomTab === 'backtest') ||
    (isMobile && layout.drawerPos !== 'closed' && layout.drawerTab === 'backtest')

  const onRightResizeStart = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      e.preventDefault()
      resizeRef.current = { startX: e.clientX, startW: layout.rightWidth }
      const onMove = (ev: PointerEvent) => {
        if (!resizeRef.current) return
        const delta = resizeRef.current.startX - ev.clientX
        const next = Math.max(280, Math.min(520, resizeRef.current.startW + delta))
        updateLayout({ rightWidth: next, rightOpen: true })
      }
      const onUp = () => {
        resizeRef.current = null
        window.removeEventListener('pointermove', onMove)
        window.removeEventListener('pointerup', onUp)
      }
      window.addEventListener('pointermove', onMove)
      window.addEventListener('pointerup', onUp)
    },
    [layout.rightWidth, updateLayout],
  )

  const openBottomTab = useCallback(
    (tab: MarketLayoutPrefs['bottomTab']) => {
      if (layout.bottomOpen && layout.bottomTab === tab) {
        updateLayout({ bottomOpen: false })
        return
      }
      updateLayout({ bottomOpen: true, bottomTab: tab, bottomHeight: layout.bottomHeight || 250 })
      if (tab === 'mark' && !markOpen && canMarkTrade) {
        /* hint only — user starts from button in panel / top bar */
      }
    },
    [layout.bottomOpen, layout.bottomTab, layout.bottomHeight, updateLayout, markOpen, canMarkTrade],
  )

  const cycleDrawer = useCallback(
    (tab?: MarketLayoutPrefs['drawerTab']) => {
      const nextTab = tab ?? layout.drawerTab
      if (tab && tab !== layout.drawerTab) {
        updateLayout({
          drawerTab: nextTab,
          drawerPos: layout.drawerPos === 'closed' ? 'half' : layout.drawerPos,
        })
        return
      }
      const order = ['closed', 'half', 'full'] as const
      const idx = order.indexOf(layout.drawerPos)
      const next = order[(idx + 1) % order.length]!
      updateLayout({ drawerPos: next, drawerTab: nextTab })
    },
    [layout.drawerPos, layout.drawerTab, updateLayout],
  )

  const setDrawerTab = useCallback(
    (tab: MarketLayoutPrefs['drawerTab']) => {
      if (layout.drawerPos === 'closed') {
        updateLayout({ drawerTab: tab, drawerPos: 'half' })
      } else if (layout.drawerTab === tab) {
        updateLayout({ drawerPos: 'closed' })
      } else {
        updateLayout({ drawerTab: tab })
      }
    },
    [layout.drawerPos, layout.drawerTab, updateLayout],
  )

  const toggleIndicator = useCallback(
    (key: IndicatorLayerKey) => {
      setLayerPrefsAndSave({ ...layerPrefs, [key]: !layerPrefs[key] })
    },
    [layerPrefs, setLayerPrefsAndSave],
  )

  const pctClass =
    change24hDisplay == null
      ? ''
      : change24hDisplay > 0
        ? 'is-up'
        : change24hDisplay < 0
          ? 'is-down'
          : ''

  return {
    setChartLive,
    setSignals,
    runClassScan,
    setBtRulesetId,
    btRulesetId,
    pinnedOnly,
    pinnedSymbols,
    instruments,
    universeError,
    marketClass,
    setMarketClass,
    symbol,
    setSymbol,
    interval,
    setInterval,
    candles,
    chartProvider,
    chartObjects,
    signals,
    chartLive,
    rows,
    chartLoading,
    scanLoading,
    error,
    layout,
    layerPrefs,
    isMobile,
    searchOpen,
    setSearchOpen,
    searchQuery,
    setSearchQuery,
    layersOpen,
    setLayersOpen,
    indicatorsOpen,
    setIndicatorsOpen,
    infoOpen,
    setInfoOpen,
    engineDetail,
    engineLoading,
    engineError,
    markOpen,
    markStep,
    markPlaced,
    markSaving,
    markError,
    btOutcome,
    btUiFilter,
    btExitReason,
    btDirection,
    btRegimeLabel,
    btObjects,
    btTrades,
    btRejected,
    btCounts,
    btMetrics,
    btActive,
    btLoading,
    btError,
    btPanelOpen,
    journalRows,
    journalLoading,
    journalError,
    indicatorsRef,
    infoRef,
    classFilter,
    allWired,
    current,
    engineOn,
    activeObjectLayerCount,
    updateLayout,
    setLayerPrefsAndSave,
    selectSymbol,
    onClassFilter,
    onSort,
    live,
    change24hDisplay,
    summaryRvol,
    enginePipeline,
    journalForSymbol,
    isTwelveData,
    providerLabel,
    canMarkTrade,
    startMarkTrade,
    cancelMarkTrade,
    onPickPoint,
    validateMarkTrade,
    clearBacktestOverlay,
    loadBacktestOverlay,
    onBtOutcome,
    onBtUiFilter,
    onBtExitReason,
    onBtDirection,
    onBtRegimeLabel,
    mergedChartObjects,
    layerCounts,
    onRightResizeStart,
    openBottomTab,
    cycleDrawer,
    setDrawerTab,
    toggleIndicator,
    pctClass,
  }
}
