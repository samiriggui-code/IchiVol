import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  pipelineFromDecisionDetail,
} from '../../lib/decisionPipeline'
import {
  getDecisionDetail,
  getScreener,
  type DecisionDetail,
  type DecisionLabel,
  type PipelineGateLabel,
  type ScreenerDecisionRow,
} from '../../lib/decisions'
import {
  getEngineUniverse,
  type EngineAssetClass,
  type EngineInstrument,
} from '../../lib/universe'
import { confirmUserDecision } from '../../lib/userDecisions'
import { listWatchlist } from '../../lib/watchlist'
import {
  getPaperOverview,
  listPaperPositions,
  openPaperPosition,
  proposePaperTrade,
  type ManualOrderInput,
  type OrderIntent,
} from '../../lib/paper'
import { useCopilotNav } from '../../lib/useCopilotNav'
import {
  CLASS_ORDER,
  compareRows,
  placeholderRow,
  rowGate,
  type ListView,
  type PaperConfirmState,
  type SortDir,
  type SortKey,
} from './shared'

export function useOpportunitesController() {
  const [searchParams, setSearchParams] = useSearchParams()
  const pinnedOnly = searchParams.get('filter') === 'pinned'
  const [pinnedSymbols, setPinnedSymbols] = useState<Set<string> | null>(null)
  const [instruments, setInstruments] = useState<EngineInstrument[]>([])
  const [marketClass, setMarketClass] = useState<EngineAssetClass>('crypto')
  const [rows, setRows] = useState<ScreenerDecisionRow[]>([])
  const [cacheAge, setCacheAge] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [selected, setSelected] = useState<string | null>(null)
  const [detail, setDetail] = useState<DecisionDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState<string | null>(null)

  const [sortKey, setSortKey] = useState<SortKey>('decision')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [symbolQuery, setSymbolQuery] = useState('')
  const [decisionFilter, setDecisionFilter] = useState<'all' | DecisionLabel>('all')
  const [gateFilter, setGateFilter] = useState<'all' | PipelineGateLabel>('all')
  const [rvolMin, setRvolMin] = useState('')
  const [actionableOnly, setActionableOnly] = useState(false)
  const [timeframe, setTimeframe] = useState('1h')
  const [whyDetail, setWhyDetail] = useState<DecisionDetail | null>(null)
  const [whyLoading, setWhyLoading] = useState(false)
  const [whyError, setWhyError] = useState<string | null>(null)

  const [confirming, setConfirming] = useState(false)
  const [confirmMsg, setConfirmMsg] = useState<string | null>(null)
  const [listView, setListView] = useState<ListView>('liste')
  const [paperBusySymbol, setPaperBusySymbol] = useState<string | null>(null)
  const [paperMsg, setPaperMsg] = useState<string | null>(null)
  const [paperConfirming, setPaperConfirming] = useState(false)
  const [paperConfirm, setPaperConfirm] = useState<PaperConfirmState | null>(null)
  const [paperConfirmError, setPaperConfirmError] = useState<string | null>(null)
  const [openPaperSymbols, setOpenPaperSymbols] = useState<ReadonlySet<string>>(() => new Set())
  const paperConfirmLock = useRef(false)
  const [intentOverride, setIntentOverride] = useState<OrderIntent | null>(null)
  const [intentLoading, setIntentLoading] = useState(false)
  const { explainDecision, compareGates } = useCopilotNav()

  const refreshOpenPaperSymbols = useCallback(async () => {
    try {
      const ov = await getPaperOverview('ICHIVOL_BASELINE_V1')
      const fromOverview = ov.positions.filter((p) => p.status === 'OPEN').map((p) => p.symbol)
      if (fromOverview.length > 0) {
        setOpenPaperSymbols(new Set(fromOverview))
        return
      }
    } catch {
      /* fallback below */
    }
    try {
      const [mine, auto] = await Promise.all([
        listPaperPositions({ source: 'user_confirmed', status: 'OPEN' }),
        listPaperPositions({ source: 'auto_watchlist', status: 'OPEN' }),
      ])
      setOpenPaperSymbols(new Set([...mine, ...auto].map((p) => p.symbol)))
    } catch {
      /* keep previous set */
    }
  }, [])

  const byId = useMemo(() => {
    const m = new Map<string, EngineInstrument>()
    for (const i of instruments) m.set(i.id, i)
    return m
  }, [instruments])

  useEffect(() => {
    if (!pinnedOnly) {
      setPinnedSymbols(null)
      return
    }
    let cancelled = false
    listWatchlist()
      .then((wl) => {
        if (!cancelled) setPinnedSymbols(new Set(wl.map((r) => r.symbol)))
      })
      .catch(() => {
        if (!cancelled) setPinnedSymbols(new Set())
      })
    return () => {
      cancelled = true
    }
  }, [pinnedOnly])

  const visibleClasses = useMemo(() => {
    const present = new Set(instruments.filter((i) => i.wired).map((i) => i.asset_class))
    return CLASS_ORDER.filter((c) => present.has(c))
  }, [instruments])

  const sheetOpen = selected != null
  const pipelineView = useMemo(
    () => (detail ? pipelineFromDecisionDetail(detail) : null),
    [detail],
  )

  /** Crypto/FX/métaux/indices : cache screener. Equity : placeholders (détail au clic). */
  const classRows = useMemo(() => {
    let base: ScreenerDecisionRow[]
    if (marketClass === 'equity') {
      base = instruments
        .filter((i) => i.asset_class === 'equity' && i.wired)
        .map((i) => {
          const hit = rows.find((r) => r.symbol === i.id)
          return hit ?? placeholderRow(i)
        })
    } else {
      base = rows.filter((r) => byId.get(r.symbol)?.asset_class === marketClass)
    }
    if (pinnedOnly && pinnedSymbols) {
      return base.filter((r) => pinnedSymbols.has(r.symbol))
    }
    return base
  }, [marketClass, instruments, rows, byId, pinnedOnly, pinnedSymbols])

  const visibleRows = useMemo(() => {
    const q = symbolQuery.trim().toLowerCase()
    const minR = rvolMin.trim() === '' ? null : Number(rvolMin)
    const filtered = classRows.filter((r) => {
      if (q) {
        const sym = r.symbol.toLowerCase()
        const label = (byId.get(r.symbol)?.label ?? '').toLowerCase()
        const short = sym.replace(/usdt$/, '')
        if (!sym.includes(q) && !short.includes(q) && !label.includes(q)) return false
      }
      if (decisionFilter !== 'all' && r.decision !== decisionFilter) return false
      if (gateFilter !== 'all') {
        const g = rowGate(r)
        if (g !== gateFilter) return false
      }
      if (actionableOnly) {
        const g = rowGate(r)
        if (g !== 'BUY' && g !== 'SELL') return false
      }
      if (minR != null && Number.isFinite(minR)) {
        if (r.rvol == null || r.rvol < minR) return false
      }
      return true
    })
    return [...filtered].sort((a, b) => compareRows(a, b, sortKey, sortDir))
  }, [
    classRows,
    symbolQuery,
    decisionFilter,
    gateFilter,
    rvolMin,
    actionableOnly,
    sortKey,
    sortDir,
    byId,
  ])

  const whyCandidate = useMemo(() => {
    if (selected) {
      const hit = classRows.find((r) => r.symbol === selected)
      if (hit) return hit
    }
    const actionable = classRows
      .filter((r) => {
        const g = rowGate(r)
        return g === 'BUY' || g === 'SELL'
      })
      .sort((a, b) => b.confidence - a.confidence)
    return actionable[0] ?? null
  }, [classRows, selected])

  useEffect(() => {
    if (!whyCandidate) {
      setWhyDetail(null)
      setWhyError(null)
      setWhyLoading(false)
      return
    }
    let cancelled = false
    setWhyLoading(true)
    setWhyError(null)
    getDecisionDetail(whyCandidate.symbol, timeframe)
      .then((d) => {
        if (!cancelled) {
          setWhyDetail(d)
          setWhyLoading(false)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setWhyDetail(null)
          setWhyError(err instanceof Error ? err.message : 'Détail indisponible')
          setWhyLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [whyCandidate?.symbol, timeframe])

  function instrumentLabel(id: string): string {
    return byId.get(id)?.label ?? id.replace(/USDT$/i, '')
  }

  function load(force = false) {
    setLoading(true)
    setError(null)
    getScreener(timeframe, force)
      .then((res) => {
        setRows(res.rows)
        setCacheAge(res.cache_age_seconds)
      })
      .catch((err: unknown) => {
        const raw = err instanceof Error ? err.message : 'Erreur de chargement'
        const lower = raw.toLowerCase()
        setError(
          lower.includes('timeout') || lower.includes('aborted') || lower.includes('dépassé')
            ? 'Timeout screener — seuils Settings custom forcent un scan live. Remets les défauts RVOL/ATR pour le cache, ou réessaie.'
            : raw,
        )
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    let cancelled = false
    getEngineUniverse()
      .then((u) => {
        if (cancelled) return
        setInstruments(u.instruments)
      })
      .catch(() => {
        /* screener seul suffit pour crypto */
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    void refreshOpenPaperSymbols()
  }, [refreshOpenPaperSymbols])

  useEffect(() => {
    load()
  }, [timeframe])

  async function onConfirmDetail() {
    if (!detail) return
    setConfirming(true)
    setConfirmMsg(null)
    try {
      const journalRow = await confirmUserDecision({
        symbol: detail.symbol,
        interval: detail.timeframe,
        bias: detail.direction,
        rvol: detail.rvol ?? 0,
        signalKind: detail.decision,
        gateDecision: detail.pipeline?.decision,
        confidence: detail.confidence,
      })
      const journalNote = journalRow.deduped ? ' (déjà au journal, mis à jour)' : ''
      setConfirmMsg(`ok${journalNote}`)
    } catch (err: unknown) {
      setConfirmMsg(err instanceof Error ? err.message : 'Échec enregistrement')
    } finally {
      setConfirming(false)
    }
  }

  async function onConfirmPaperOrder() {
    const intent = intentOverride ?? detail?.order_intent ?? null
    if (!detail) return
    if (openPaperSymbols.has(detail.symbol)) {
      setPaperMsg(`${detail.symbol} · déjà ouvert — pas de 2ᵉ achat`)
      setConfirmMsg('Déjà une position ouverte sur ce symbole')
      return
    }
    setPaperConfirmError(null)
    setPaperConfirm({
      symbol: detail.symbol,
      timeframe: detail.timeframe,
      intent,
      source: 'sheet',
    })
  }

  async function executePaperConfirm(order: ManualOrderInput) {
    if (!paperConfirm || paperConfirmLock.current) return
    paperConfirmLock.current = true
    setPaperConfirming(true)
    setConfirmMsg(null)
    setPaperMsg(null)
    setPaperConfirmError(null)
    try {
      const sameDetail = detail?.symbol === paperConfirm.symbol ? detail : null
      const gate = paperConfirm.intent?.pipeline_decision ?? sameDetail?.pipeline?.decision ?? 'WATCH'
      // Ordre : le moteur d'abord. Un refus (Portes repassées à Attente, fonds…) lève ici,
      // avant toute écriture au journal — ni position, ni « confirmation » orpheline.
      const pos = await openPaperPosition(paperConfirm.symbol, paperConfirm.timeframe, order)
      let journalWarn = ''
      try {
        await confirmUserDecision({
          symbol: paperConfirm.symbol,
          interval: paperConfirm.timeframe,
          bias: 'BULLISH',
          rvol: sameDetail?.rvol ?? 0,
          signalKind:
            sameDetail?.decision ??
            (gate === 'SELL' ? 'SELL' : gate === 'BUY' ? 'BUY' : 'WATCH'),
          gateDecision: gate,
          confidence: sameDetail?.confidence,
        })
      } catch {
        // La position existe : on le dit, on ne prétend pas que le journal est à jour.
        journalWarn = ' · journal non enregistré (réessayer depuis le Journal)'
      }
      const already = pos.already_open === true || pos.created === false
      const msg = already
        ? `déjà ouvert · ${pos.symbol} ${pos.direction} (pas de 2ᵉ notional)`
        : `ok · paper ${pos.direction} qty ${pos.qty != null ? pos.qty.toPrecision(4) : '—'}`
      setConfirmMsg(msg + journalWarn)
      setPaperMsg(
        (already
          ? `${pos.symbol} · déjà en portefeuille — achat verrouillé`
          : `${pos.symbol} · paper ${pos.direction} @ ${pos.entry_price}`) + journalWarn,
      )
      setOpenPaperSymbols((prev) => new Set([...prev, pos.symbol]))
      setPaperConfirm(null)
      void refreshOpenPaperSymbols()
    } catch (err: unknown) {
      const raw = err instanceof Error ? err.message : 'Échec paper'
      const stale = false
      const msg = raw.replace(/^[a-z_]+: /, '')
      setConfirmMsg(msg)
      setPaperMsg(msg)
      setPaperConfirmError(msg)
      if (stale) {
        try {
          const fresh = await proposePaperTrade(paperConfirm.symbol, paperConfirm.timeframe)
          setPaperConfirm((cur) => (cur ? { ...cur, intent: fresh } : cur))
        } catch {
          /* le message d'erreur reste affiché */
        }
      }
    } finally {
      setPaperConfirming(false)
      paperConfirmLock.current = false
    }
  }

  async function onOpenPaperFromMatrix(row: ScreenerDecisionRow) {
    if (openPaperSymbols.has(row.symbol) || paperBusySymbol) return
    setPaperBusySymbol(row.symbol)
    setPaperMsg(null)
    setPaperConfirmError(null)
    try {
      // La proposition du moteur sert de taille suggérée ; son absence n'empêche pas d'acheter.
      const intent = await proposePaperTrade(row.symbol, row.timeframe || timeframe).catch(() => null)
      setPaperConfirm({
        symbol: row.symbol,
        timeframe: row.timeframe || timeframe,
        intent,
        source: 'matrix',
      })
    } finally {
      setPaperBusySymbol(null)
    }
  }

  async function onRefreshIntent() {
    if (!detail) return
    setIntentLoading(true)
    try {
      setIntentOverride(await proposePaperTrade(detail.symbol, detail.timeframe || timeframe))
    } catch {
      setIntentOverride(null)
    } finally {
      setIntentLoading(false)
    }
  }

  // Toujours avoir un intent pour afficher « Vérifier l’achat… » → PaperConfirmSheet.
  useEffect(() => {
    if (!detail) return
    if (detail.order_intent || intentOverride) return
    let cancelled = false
    setIntentLoading(true)
    proposePaperTrade(detail.symbol, detail.timeframe || timeframe)
      .then((intent) => {
        if (!cancelled) setIntentOverride(intent)
      })
      .catch(() => {
        if (!cancelled) setIntentOverride(null)
      })
      .finally(() => {
        if (!cancelled) setIntentLoading(false)
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload when symbol/tf change
  }, [detail?.symbol, detail?.timeframe, detail?.order_intent])

  function selectClass(next: EngineAssetClass) {
    setMarketClass(next)
    setSelected(null)
    setDetail(null)
    setDetailError(null)
    setSymbolQuery('')
    setIntentOverride(null)
    setConfirmMsg(null)
  }

  useEffect(() => {
    if (!sheetOpen) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') closeSheet()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [sheetOpen])

  function closeSheet() {
    setSelected(null)
    setDetail(null)
    setDetailError(null)
    setDetailLoading(false)
    setIntentOverride(null)
    setConfirmMsg(null)
    if (searchParams.has('symbol')) {
      const next = new URLSearchParams(searchParams)
      next.delete('symbol')
      setSearchParams(next, { replace: true })
    }
  }

  function onSelect(symbol: string) {
    if (selected === symbol) {
      closeSheet()
      return
    }
    const inst = byId.get(symbol)
    if (inst) setMarketClass(inst.asset_class)
    setSelected(symbol)
    setDetail(null)
    setDetailError(null)
    setDetailLoading(true)
    setIntentOverride(null)
    setConfirmMsg(null)
    const next = new URLSearchParams(searchParams)
    next.set('symbol', symbol)
    setSearchParams(next, { replace: false })
    getDecisionDetail(symbol, timeframe)
      .then(setDetail)
      .catch((err: unknown) =>
        setDetailError(err instanceof Error ? err.message : 'Erreur de chargement'),
      )
      .finally(() => setDetailLoading(false))
  }

  useEffect(() => {
    const fromUrl = searchParams.get('symbol')
    const classQ = searchParams.get('class')
    const intervalQ = searchParams.get('interval')
    if (
      intervalQ === '15m' ||
      intervalQ === '1h' ||
      intervalQ === '4h' ||
      intervalQ === '1d'
    ) {
      setTimeframe(intervalQ)
    }
    if (
      classQ === 'crypto' ||
      classQ === 'forex' ||
      classQ === 'metal' ||
      classQ === 'index' ||
      classQ === 'equity' ||
      classQ === 'energy'
    ) {
      setMarketClass(classQ)
    }
    if (!fromUrl) {
      if (selected) {
        setSelected(null)
        setDetail(null)
        setDetailError(null)
        setDetailLoading(false)
        setIntentOverride(null)
        setConfirmMsg(null)
      }
      return
    }
    if (selected === fromUrl) return
    setSelected(fromUrl)
    setDetail(null)
    setDetailError(null)
    setDetailLoading(true)
    setIntentOverride(null)
    setConfirmMsg(null)
    const tf =
      intervalQ === '15m' ||
      intervalQ === '1h' ||
      intervalQ === '4h' ||
      intervalQ === '1d'
        ? intervalQ
        : timeframe
    getDecisionDetail(fromUrl, tf)
      .then((d) => {
        setDetail(d)
        const inst = instruments.find((i) => i.id === fromUrl)
        if (inst) setMarketClass(inst.asset_class)
      })
      .catch((err: unknown) =>
        setDetailError(err instanceof Error ? err.message : 'Erreur de chargement'),
      )
      .finally(() => setDetailLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps -- deep-link once per symbol query
  }, [searchParams, instruments])

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
      return
    }
    setSortKey(key)
    setSortDir(key === 'symbol' ? 'asc' : 'desc')
  }

  const colCount = sheetOpen ? 3 : 6
  const activeIntent: OrderIntent | null = intentOverride ?? detail?.order_intent ?? null

  const gateStats = useMemo(() => {
    let buy = 0
    let sell = 0
    let watch = 0
    let none = 0
    for (const r of classRows) {
      const g = rowGate(r)
      if (g === 'BUY') buy += 1
      else if (g === 'SELL') sell += 1
      else if (g === 'WATCH') watch += 1
      else none += 1
    }
    return { buy, sell, watch, none, total: classRows.length }
  }, [classRows])


  return {
    searchParams,
    setSearchParams,
    pinnedOnly,
    pinnedSymbols,
    instruments,
    marketClass,
    setMarketClass,
    rows,
    cacheAge,
    loading,
    error,
    selected,
    detail,
    detailLoading,
    detailError,
    sortKey,
    sortDir,
    symbolQuery,
    setSymbolQuery,
    decisionFilter,
    setDecisionFilter,
    gateFilter,
    setGateFilter,
    rvolMin,
    setRvolMin,
    actionableOnly,
    setActionableOnly,
    timeframe,
    setTimeframe,
    whyDetail,
    whyLoading,
    whyError,
    confirming,
    confirmMsg,
    listView,
    setListView,
    paperBusySymbol,
    paperMsg,
    paperConfirming,
    paperConfirm,
    setPaperConfirm,
    paperConfirmError,
    openPaperSymbols,
    intentOverride,
    intentLoading,
    explainDecision,
    compareGates,
    byId,
    visibleClasses,
    sheetOpen,
    pipelineView,
    classRows,
    visibleRows,
    whyCandidate,
    instrumentLabel,
    load,
    onConfirmDetail,
    onConfirmPaperOrder,
    executePaperConfirm,
    onOpenPaperFromMatrix,
    onRefreshIntent,
    selectClass,
    closeSheet,
    onSelect,
    toggleSort,
    colCount,
    activeIntent,
    gateStats,
  }
}
