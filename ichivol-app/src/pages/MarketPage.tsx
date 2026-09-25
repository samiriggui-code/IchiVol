import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
} from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { BiasPanel } from '../components/BiasPanel'
import {
  BacktestOverlaySheet,
  type BacktestUiFilter,
} from '../components/BacktestOverlaySheet'
import { MarkTradeSheet, type MarkTradeStep } from '../components/MarkTradeSheet'
import { MarketLayersMenu } from '../components/MarketLayersMenu'
import { MarketSymbolSearch } from '../components/MarketSymbolSearch'
import { MarketWatchlist, buildContextBadges } from '../components/MarketWatchlist'
import { PriceChart, type ChartPickPoint } from '../components/PriceChart'
import { INTERVALS } from '../lib/binance'
import {
  getDecisionDetail,
  getScreener,
  type DecisionDetail,
  type ScreenerDecisionRow,
} from '../lib/decisions'
import { pipelineFromDecisionDetail } from '../lib/decisionPipeline'
import { labelDecision, labelPipelineGate } from '../lib/decisionLabels'
import { displaySymbol } from '../lib/markets'
import {
  listUserDecisions,
  type UserDecisionRow,
} from '../lib/userDecisions'
import './MarketPage.css'
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
import type { BacktestMetrics } from '../lib/backtest'
import { useMarketSnapshot } from '../lib/marketSnapshot'
import { listWatchlist } from '../lib/watchlist'
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
} from '../lib/marketPrefs'
import {
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

const INDICATOR_TOGGLES: { key: IndicatorLayerKey; label: string }[] = [
  { key: 'candles', label: 'Bougies' },
  { key: 'tenkan', label: 'Tenkan' },
  { key: 'kijun', label: 'Kijun' },
  { key: 'spanA', label: 'Span A' },
  { key: 'spanB', label: 'Span B' },
  { key: 'volume', label: 'Volume' },
  { key: 'signals', label: 'Signaux' },
]

function newSetupId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `setup-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}

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

function fmtPrice(n: number | null): string {
  if (n == null || !Number.isFinite(n)) return '—'
  return n.toLocaleString('fr-FR', { maximumFractionDigits: n >= 100 ? 2 : 6 })
}

function fmtPct(n: number | null): string {
  if (n == null || !Number.isFinite(n)) return '—'
  const sign = n > 0 ? '+' : ''
  return `${sign}${n.toLocaleString('fr-FR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} %`
}

function fmtRvol(n: number | null): string {
  if (n == null || !Number.isFinite(n)) return '—'
  return `${n.toLocaleString('fr-FR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}×`
}

/** Variation ≈24h depuis les bougies OHLCV (jamais inventée). */
function change24hFromCandles(candles: Candle[]): number | null {
  if (candles.length < 2) return null
  const last = candles[candles.length - 1]
  if (!last || !Number.isFinite(last.close) || last.close === 0) return null
  const target = last.time - 24 * 3600
  let best = candles[0]
  let bestDist = Math.abs((best?.time ?? 0) - target)
  for (let i = 1; i < candles.length - 1; i++) {
    const c = candles[i]
    if (!c) continue
    const dist = Math.abs(c.time - target)
    if (dist < bestDist) {
      best = c
      bestDist = dist
    }
  }
  if (!best || !Number.isFinite(best.close) || best.close === 0) return null
  // Pas assez d’historique (~<12h) → Non disponible plutôt qu’un faux 24h.
  if (last.time - best.time < 12 * 3600) return null
  return ((last.close - best.close) / best.close) * 100
}

function journalGateLabel(row: UserDecisionRow): string {
  if (row.gateDecision) {
    return labelPipelineGate(row.gateDecision as 'BUY' | 'SELL' | 'WATCH' | 'NO_TRADE')
  }
  if (row.signalKind) {
    return labelDecision(
      row.signalKind as
        | 'STRONG_BUY'
        | 'BUY'
        | 'WATCH'
        | 'WAIT'
        | 'SELL'
        | 'STRONG_SELL',
    )
  }
  return 'Non disponible'
}

function isAssetClass(v: string | null): v is EngineAssetClass {
  return (
    v === 'crypto' ||
    v === 'forex' ||
    v === 'metal' ||
    v === 'index' ||
    v === 'equity' ||
    v === 'energy'
  )
}

export function MarketPage() {
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
  /** Ephemeral layer force-on (mark trade / backtest) — not persisted. */
  const [layerOverrides, setLayerOverrides] = useState<Partial<LayerPrefs>>({})
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

  const effectiveLayerPrefs = useMemo(
    () => ({ ...layerPrefs, ...layerOverrides }),
    [layerPrefs, layerOverrides],
  )

  const activeObjectLayerCount = useMemo(
    () => OBJECT_LAYER_META.filter((m) => effectiveLayerPrefs[m.key]).length,
    [effectiveLayerPrefs],
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

  const pushLayerOverride = useCallback((key: 'user_trades' | 'backtest') => {
    setLayerOverrides((prev) => ({ ...prev, [key]: true }))
  }, [])

  const popLayerOverride = useCallback((key: 'user_trades' | 'backtest') => {
    setLayerOverrides((prev) => {
      if (!(key in prev)) return prev
      const next = { ...prev }
      delete next[key]
      return next
    })
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
          return { ...row, context: buildContextBadges(row) }
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
    pushLayerOverride('user_trades')
  }, [pushLayerOverride])

  const cancelMarkTrade = useCallback(() => {
    setMarkOpen(false)
    setMarkStep('entry')
    setMarkPlaced({})
    setMarkSetupId(null)
    setMarkError(null)
    setMarkSaving(false)
    popLayerOverride('user_trades')
  }, [popLayerOverride])

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
    popLayerOverride('backtest')
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
    popLayerOverride('backtest')
  }, [popLayerOverride])

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
        pushLayerOverride('backtest')
      } catch (err: unknown) {
        setBtError(err instanceof Error ? err.message : 'Échec backtest')
      } finally {
        setBtLoading(false)
      }
    },
    [
      btRulesetId,
      btOutcome,
      btExitReason,
      btDirection,
      btRegimeLabel,
      symbol,
      interval,
      pushLayerOverride,
    ],
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

  const watchlistProps = {
    rows: pinnedOnly && pinnedSymbols
      ? rows.filter((r) => pinnedSymbols.has(r.symbol))
      : rows,
    instruments,
    loading: scanLoading || (pinnedOnly && pinnedSymbols == null),
    selected: symbol,
    onSelect: selectSymbol,
    sortKey: layout.sortKey,
    sortDir: layout.sortDir,
    onSort,
    classFilter,
    onClassFilter,
    onRescan: () => void runClassScan(interval, instruments),
    scanLoading,
    showEngine: engineOn || marketClass === 'crypto' || allWired.some((i) => i.provider !== 'twelve_data'),
  }

  const prepareHint = canMarkTrade
    ? null
    : 'Disponible sur symboles câblés (timeframes moteur 15m / 1h / 4h / 1d).'

  const biasPanel = (
    <BiasPanel
      symbol={current?.label ?? displaySymbol(symbol)}
      signals={signals}
      bias={live.bias}
      rvol={summaryRvol}
      price={live.price}
      engineDetail={engineDetail}
      enginePipeline={enginePipeline}
      engineLoading={engineLoading}
      engineError={engineError}
      engineAvailable={engineOn}
      onPrepareTrade={() => {
        if (!canMarkTrade || markSaving) return
        startMarkTrade()
        if (isMobile) updateLayout({ drawerPos: 'closed' })
      }}
      prepareTradeDisabled={!canMarkTrade || markSaving}
      prepareTradeHint={prepareHint}
    />
  )

  const chartSummary = (
    <div className="mkt-chart-summary" aria-label="Résumé PRIX 24H RVOL">
      <span>
        Prix <b className="mono">{fmtPrice(live.price)}</b>
      </span>
      <span>
        24H{' '}
        <b className={`mono ${change24hDisplay == null ? 'is-na' : pctClass}`}>
          {change24hDisplay == null ? 'Non disponible' : fmtPct(change24hDisplay)}
        </b>
      </span>
      <span>
        RVOL <b className={`mono ${summaryRvol == null ? 'is-na' : ''}`}>{fmtRvol(summaryRvol)}</b>
      </span>
    </div>
  )

  const chartEl = (
    <PriceChart
      candles={candles}
      symbol={symbol}
      timeframe={interval}
      onSignals={setSignals}
      onLive={setChartLive}
      chartObjects={mergedChartObjects}
      pickMode={markOpen && markStep !== 'review'}
      onPickPoint={onPickPoint}
      layerPrefs={effectiveLayerPrefs}
      onLayerPrefsChange={setLayerPrefsAndSave}
      volumeHeight={isMobile ? Math.min(layout.volumeHeight, 120) : layout.volumeHeight}
      onVolumeHeightChange={(h) => updateLayout({ volumeHeight: h })}
    />
  )

  const backtestEmbed = btPanelOpen ? (
    <BacktestOverlaySheet
      symbolLabel={current?.label ?? displaySymbol(symbol)}
      selectedRulesetId={btRulesetId}
      outcome={btOutcome}
      uiFilter={btUiFilter}
      counts={btCounts}
      trades={btTrades}
      rejected={btRejected}
      metrics={btMetrics}
      exitReason={btExitReason}
      direction={btDirection}
      regimeLabel={btRegimeLabel}
      loading={btLoading}
      error={btError}
      active={btActive}
      variant="embed"
      onSelectRuleset={setBtRulesetId}
      onOutcome={onBtOutcome}
      onUiFilter={onBtUiFilter}
      onExitReason={onBtExitReason}
      onDirection={onBtDirection}
      onRegimeLabel={onBtRegimeLabel}
      onShow={() => void loadBacktestOverlay(btOutcome)}
      onClear={clearBacktestOverlay}
      onClose={() => {
        if (isMobile) updateLayout({ drawerPos: 'closed' })
        else updateLayout({ bottomOpen: false })
      }}
    />
  ) : null

  const tfButtons = (
    <div className="mkt-tf-group" role="group" aria-label="Timeframe">
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
  )

  const infoButton = (
    <div className="mkt-info-wrap" ref={infoRef}>
      <button
        type="button"
        className="mkt-icon-btn"
        aria-label="Info source"
        aria-expanded={infoOpen}
        onClick={() => setInfoOpen((o) => !o)}
      >
        i
      </button>
      {infoOpen ? (
        <div className="mkt-info-pop" role="note">
          {isTwelveData
            ? `Données via le moteur IchiVol (${providerLabel}) — pas de compte broker. Plan Twelve Data gratuit ≈ 8 crédits/min : charge un symbole à la fois (liste sans scan parallèle).`
            : `Source : ${providerLabel}. OHLCV via le moteur IchiVol — pas de compte broker.`}
        </div>
      ) : null}
    </div>
  )

  return (
    <div
      className={`market-page mkt-page${isMobile ? ' is-mobile' : ' is-desktop'}${
        markOpen ? ' is-mark-trade' : ''
      }${btPanelOpen ? ' is-backtest-overlay' : ''}${
        layout.rightOpen ? '' : ' is-right-collapsed'
      }${layout.bottomOpen ? ' is-bottom-open' : ''}`}
      style={
        {
          '--mkt-right-w': `${layout.rightWidth}px`,
          '--mkt-bottom-h': `${layout.bottomHeight}px`,
          '--mkt-drawer-pos': layout.drawerPos,
        } as CSSProperties
      }
      data-drawer={layout.drawerPos}
    >
      {/* —— Desktop top bar —— */}
      {!isMobile && (
        <header className="mkt-topbar" style={{ height: 52 }}>
          <button
            type="button"
            className="mkt-symbol-btn"
            aria-haspopup="dialog"
            aria-expanded={searchOpen}
            onClick={() => setSearchOpen((o) => !o)}
          >
            <span className="mkt-symbol-label">
              {current?.label ?? displaySymbol(symbol)}
            </span>
            <span className="mkt-caret" aria-hidden>
              ▾
            </span>
          </button>

          <div className="mkt-quote">
            <span className="mkt-price mono">{fmtPrice(live.price)}</span>
            <span className={`mkt-pct mono ${pctClass}`}>{fmtPct(change24hDisplay)}</span>
            <span className="mkt-source muted">{providerLabel}</span>
            {chartLoading ? <span className="muted">…</span> : null}
          </div>

          {tfButtons}

          <div className="mkt-topbar-actions">
            <div className="mkt-menu-anchor">
              <button
                type="button"
                className="ghost mkt-topbar-btn"
                aria-expanded={layersOpen}
                onClick={() => {
                  setLayersOpen((o) => !o)
                  setIndicatorsOpen(false)
                }}
              >
                Calques{activeObjectLayerCount ? ` · ${activeObjectLayerCount}` : ''} ▾
              </button>
              {layersOpen ? (
                <MarketLayersMenu
                  open
                  onClose={() => setLayersOpen(false)}
                  prefs={layerPrefs}
                  onChange={setLayerPrefsAndSave}
                  counts={layerCounts}
                  variant="menu"
                />
              ) : null}
            </div>

            <div className="mkt-menu-anchor" ref={indicatorsRef}>
              <button
                type="button"
                className="ghost mkt-topbar-btn"
                aria-expanded={indicatorsOpen}
                onClick={() => {
                  setIndicatorsOpen((o) => !o)
                  setLayersOpen(false)
                }}
              >
                Indicateurs ▾
              </button>
              {indicatorsOpen ? (
                <div className="mkt-indicators-menu" role="menu">
                  {INDICATOR_TOGGLES.map((t) => (
                    <button
                      key={t.key}
                      type="button"
                      role="menuitemcheckbox"
                      aria-checked={layerPrefs[t.key]}
                      className={layerPrefs[t.key] ? 'is-on' : undefined}
                      onClick={() => toggleIndicator(t.key)}
                    >
                      <span aria-hidden>{layerPrefs[t.key] ? '◉' : '○'}</span>
                      {t.label}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>

            <span className="mkt-topbar-ellipsis" aria-hidden>
              …
            </span>

            {infoButton}

            <button
              type="button"
              className={markOpen ? 'is-active mkt-topbar-btn' : 'ghost mkt-topbar-btn'}
              disabled={!canMarkTrade || markSaving}
              title={
                canMarkTrade
                  ? 'Poser ENTRY / STOP / TARGET sur le graphique'
                  : 'Disponible sur symboles câblés (TF moteur)'
              }
              onClick={() => {
                if (markOpen) cancelMarkTrade()
                else {
                  startMarkTrade()
                  updateLayout({ bottomOpen: true, bottomTab: 'mark' })
                }
              }}
            >
              {markOpen ? 'Annuler marquage' : 'Marquer un trade'}
            </button>

            <button
              type="button"
              className="side-toggle mkt-icon-btn"
              aria-expanded={layout.rightOpen}
              aria-controls="mkt-right"
              title={layout.rightOpen ? 'Réduire le panneau' : 'Afficher le panneau'}
              onClick={() => updateLayout({ rightOpen: !layout.rightOpen })}
            >
              {layout.rightOpen ? '⟩' : '⟨'}
            </button>
          </div>

          {searchOpen ? (
            <MarketSymbolSearch
              open
              onClose={() => setSearchOpen(false)}
              instruments={instruments}
              rows={rows}
              selected={symbol}
              search={searchQuery}
              onSearch={setSearchQuery}
              classFilter={classFilter}
              onClassFilter={onClassFilter}
              onSelect={selectSymbol}
              variant="popover"
            />
          ) : null}
        </header>
      )}

      {/* —— Mobile top bar —— */}
      {isMobile && (
        <>
          <header className="mkt-topbar mkt-topbar--mobile" style={{ minHeight: 52 }}>
            <button
              type="button"
              className="mkt-symbol-btn"
              style={{ minWidth: 44, minHeight: 44 }}
              aria-haspopup="dialog"
              aria-expanded={searchOpen}
              onClick={() => setSearchOpen(true)}
            >
              <span className="mkt-symbol-label">
                {current?.label ?? displaySymbol(symbol)}
              </span>
              <span className="mkt-caret" aria-hidden>
                ▾
              </span>
            </button>
            <div className="mkt-quote">
              <span className="mkt-price mono">{fmtPrice(live.price)}</span>
              <span className={`mkt-pct mono ${pctClass}`}>{fmtPct(change24hDisplay)}</span>
            </div>
            <button
              type="button"
              className="mkt-icon-btn"
              style={{ minWidth: 44, minHeight: 44 }}
              aria-label="Rechercher"
              onClick={() => setSearchOpen(true)}
            >
              ⌕
            </button>
            <button
              type="button"
              className="mkt-icon-btn"
              style={{ minWidth: 44, minHeight: 44 }}
              aria-label="Calques"
              aria-expanded={layersOpen}
              onClick={() => setLayersOpen(true)}
            >
              Calques
            </button>
          </header>
          <div className="mkt-mobile-tf-row">
            {tfButtons}
            {infoButton}
          </div>
        </>
      )}

      {(error || universeError) && (
        <div className="banner error mkt-error-toast" role="alert">
          {error ?? universeError}
        </div>
      )}
      {pinnedOnly && (
        <div className="banner mkt-pinned-banner" role="status">
          Filtre <strong>Épinglés</strong> (watchlist) —{' '}
          <a href="/app/market">voir tout le marché</a>
        </div>
      )}

      {/* —— Main layout —— */}
      <div className="mkt-body">
        <section className="mkt-chart-panel chart-panel panel">
          {chartSummary}
          {chartEl}
        </section>

        {!isMobile && layout.rightOpen && (
          <>
            <div
              className="mkt-resize-handle"
              role="separator"
              aria-orientation="vertical"
              aria-label="Redimensionner la colonne"
              onPointerDown={onRightResizeStart}
            />
            <aside id="mkt-right" className="mkt-right side">
              <div className="mkt-right-list">
                <MarketWatchlist {...watchlistProps} />
              </div>
              <div className="mkt-right-bias">{biasPanel}</div>
            </aside>
          </>
        )}
      </div>

      {/* —— Desktop bottom dock —— */}
      {!isMobile && (
        <div className="mkt-bottom-dock">
          {layout.bottomOpen && (
            <div
              className="mkt-bottom-panel"
              style={{ height: layout.bottomHeight || 250 }}
            >
              {layout.bottomTab === 'backtest' ? backtestEmbed : null}
              {layout.bottomTab === 'mark' ? (
                <div className="mkt-bottom-embed">
                  <p>
                    {markOpen
                      ? `Mode marquage — étape : ${markStep}. Clique le graphique pour poser les points.`
                      : 'Pose ENTRY → STOP → TARGET sur le graphique, puis valide.'}
                  </p>
                  <button
                    type="button"
                    className={markOpen ? 'is-active' : undefined}
                    disabled={!canMarkTrade || markSaving}
                    onClick={() => (markOpen ? cancelMarkTrade() : startMarkTrade())}
                  >
                    {markOpen ? 'Annuler' : 'Démarrer'}
                  </button>
                </div>
              ) : null}
              {layout.bottomTab === 'journal' ? (
                <div className="mkt-bottom-embed mkt-journal-dock">
                  <div className="mkt-journal-dock-head">
                    <h3>Journal · {current?.label ?? displaySymbol(symbol)}</h3>
                    <Link className="mkt-journal-dock-link" to="/app/journal">
                      Ouvrir le journal →
                    </Link>
                  </div>
                  {journalLoading ? (
                    <p className="mkt-journal-dock-msg">Chargement…</p>
                  ) : journalError ? (
                    <p className="mkt-journal-dock-msg is-error" role="alert">
                      {journalError}
                    </p>
                  ) : journalForSymbol.length === 0 ? (
                    <p className="mkt-journal-dock-msg">
                      Aucune décision sauvegardée pour ce symbole.
                    </p>
                  ) : (
                    <ul className="mkt-journal-list">
                      {journalForSymbol.slice(0, 12).map((row) => (
                        <li key={row.id}>
                          <span className="mkt-journal-when mono">
                            {new Date(row.createdAt).toLocaleString('fr-FR', {
                              day: '2-digit',
                              month: 'short',
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </span>
                          <span className="mkt-journal-meta">
                            {row.interval}
                            {row.note ? ` · ${row.note}` : ''}
                          </span>
                          <span className="mkt-journal-gate">{journalGateLabel(row)}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ) : null}
            </div>
          )}
          <nav className="mkt-bottom-bar" style={{ height: 44 }} aria-label="Panneau bas">
            {(
              [
                ['backtest', 'Backtest'],
                ['mark', 'Marquer un trade'],
                ['journal', 'Journal'],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                className={
                  layout.bottomOpen && layout.bottomTab === id ? 'is-active' : undefined
                }
                disabled={id === 'backtest' ? !canMarkTrade && !btActive : false}
                onClick={() => openBottomTab(id)}
              >
                {label}
              </button>
            ))}
          </nav>
        </div>
      )}

      {/* —— Mobile bottom drawer —— */}
      {isMobile && (
        <div className={`mkt-drawer is-${layout.drawerPos}`} data-pos={layout.drawerPos}>
          <button
            type="button"
            className="mkt-drawer-handle"
            aria-label="Hauteur du tiroir"
            onClick={() => cycleDrawer()}
          />
          <nav className="mkt-drawer-tabs" aria-label="Tiroir">
            {(
              [
                ['list', 'Liste'],
                ['analysis', 'Analyse'],
                ['backtest', 'Backtest'],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                className={
                  layout.drawerPos !== 'closed' && layout.drawerTab === id
                    ? 'is-active'
                    : undefined
                }
                style={{ minHeight: 44 }}
                onClick={() => setDrawerTab(id)}
              >
                {label}
              </button>
            ))}
          </nav>
          {layout.drawerPos !== 'closed' && (
            <div className="mkt-drawer-body">
              {layout.drawerTab === 'list' ? (
                <MarketWatchlist {...watchlistProps} hideScore />
              ) : null}
              {layout.drawerTab === 'analysis' ? (
                <div className="mkt-analysis-mobile">
                  {biasPanel}
                </div>
              ) : null}
              {layout.drawerTab === 'backtest' ? backtestEmbed : null}
            </div>
          )}
        </div>
      )}

      {isMobile && searchOpen ? (
        <MarketSymbolSearch
          open
          onClose={() => setSearchOpen(false)}
          instruments={instruments}
          rows={rows}
          selected={symbol}
          search={searchQuery}
          onSearch={setSearchQuery}
          classFilter={classFilter}
          onClassFilter={onClassFilter}
          onSelect={selectSymbol}
          variant="sheet"
        />
      ) : null}

      {isMobile && layersOpen ? (
        <MarketLayersMenu
          open
          onClose={() => setLayersOpen(false)}
          prefs={layerPrefs}
          onChange={setLayerPrefsAndSave}
          counts={layerCounts}
          variant="sheet"
        />
      ) : null}

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
    </div>
  )
}
