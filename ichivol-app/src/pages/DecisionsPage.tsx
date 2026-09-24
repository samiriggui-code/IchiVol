import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { DecisionPipelinePanel } from '../components/DecisionPipelinePanel'
import { PaperConfirmSheet } from '../components/PaperConfirmSheet'
import { ProposePaperTradePanel } from '../components/ProposePaperTradePanel'
import { SignalEvidenceCard } from '../components/SignalEvidenceCard'
import { TradePlanCard } from '../components/TradePlanCard'
import { VerdictBadge } from '../components/VerdictBadge'
import {
  buildDecisionSummary,
  labelDecision,
  labelDirection,
  labelPipelineGate,
  labelReason,
} from '../lib/decisionLabels'
import {
  pipelineFromDecisionDetail,
  stageStatusesFromRow,
  type PipelineStageStatus,
} from '../lib/decisionPipeline'
import {
  getDecisionDetail,
  getScreener,
  type AgentDetail,
  type DecisionDetail,
  type DecisionLabel,
  type PipelineGateLabel,
  type ScreenerDecisionRow,
} from '../lib/decisions'
import {
  CLASS_BLURBS,
  CLASS_LABELS,
  getEngineUniverse,
  type EngineAssetClass,
  type EngineInstrument,
} from '../lib/universe'
import { confirmUserDecision } from '../lib/userDecisions'
import { listWatchlist } from '../lib/watchlist'
import {
  getPaperOverview,
  listPaperPositions,
  openPaperPosition,
  proposePaperTrade,
  type ManualOrderInput,
  type OrderIntent,
} from '../lib/paper'
import { decisionPayloadFromDetail } from '../lib/agent'
import { useCopilotNav } from '../lib/useCopilotNav'
import { Tag, WorkspacePageHead } from '../components/maquette'
type SortKey = 'symbol' | 'decision' | 'confidence' | 'ichimoku_score' | 'rvol' | 'price'
type SortDir = 'asc' | 'desc'
type CycleStage = 'WATCH' | 'ARMED' | 'TRIGGERED'
type CycleFilter = 'Tous' | CycleStage

const CYCLE_FILTERS: CycleFilter[] = ['Tous', 'WATCH', 'ARMED', 'TRIGGERED']
const FLOW_STAGES = ['WATCH', 'ARMED', 'TRIGGERED', 'ACCEPTÉ', 'REFUSÉ'] as const

const CLASS_ORDER: EngineAssetClass[] = [
  'crypto',
  'forex',
  'metal',
  'index',
  'equity',
  'energy',
]

/** Equity Twelve Data : hors cache screener (crédits) — lignes locales, détail au clic. */
function placeholderRow(inst: EngineInstrument): ScreenerDecisionRow {
  return {
    symbol: inst.id,
    timeframe: '1h',
    price: 0,
    decision: 'WAIT',
    direction: 'NEUTRAL',
    confidence: 0,
    probability: 0,
    ichimoku_score: null,
    rvol: null,
  }
}

const DECISION_RANK: Record<DecisionLabel, number> = {
  STRONG_BUY: 6,
  BUY: 5,
  WATCH: 4,
  WAIT: 3,
  SELL: 2,
  STRONG_SELL: 1,
}

const GATE_RANK: Record<PipelineGateLabel, number> = {
  BUY: 4,
  SELL: 3,
  WATCH: 2,
  NO_TRADE: 1,
}

function rowGate(r: ScreenerDecisionRow): PipelineGateLabel | null {
  const raw = r.pipeline?.decision
  if (raw === 'BUY' || raw === 'SELL' || raw === 'WATCH' || raw === 'NO_TRADE') return raw
  return null
}

function cycleFromRow(row: ScreenerDecisionRow): CycleStage {
  const gate = rowGate(row)
  if (gate === 'BUY' || gate === 'SELL') return 'TRIGGERED'
  const st = stageStatusesFromRow(row)
  if (st.direction === 'pass' && st.participation !== 'pass') return 'ARMED'
  if (gate === 'WATCH' && st.direction === 'pass') return 'ARMED'
  return 'WATCH'
}

function gateBadgeLabel(status: PipelineStageStatus): string {
  switch (status) {
    case 'pass':
      return 'PASSE'
    case 'fail':
      return 'BLOQUÉ'
    case 'watch':
      return 'PRUDENCE'
    case 'pending':
      return '—'
    case 'skip':
      return 'N/A'
    default: {
      const _exhaustive: never = status
      return _exhaustive
    }
  }
}

function gateBadgeClass(status: PipelineStageStatus): string {
  switch (status) {
    case 'pass':
      return 'tag green'
    case 'fail':
      return 'tag red'
    case 'watch':
      return 'tag amber'
    case 'pending':
    case 'skip':
      return 'tag gray'
    default: {
      const _exhaustive: never = status
      return _exhaustive
    }
  }
}

function cycleBadgeClass(cycle: CycleStage): string {
  switch (cycle) {
    case 'TRIGGERED':
      return 'tag amber'
    case 'ARMED':
      return 'tag green'
    case 'WATCH':
      return 'tag gray'
    default: {
      const _exhaustive: never = cycle
      return _exhaustive
    }
  }
}

function directionCell(row: ScreenerDecisionRow): { text: string; tone: 'up' | 'down' | '' } {
  const gate = rowGate(row)
  if (gate === 'SELL' || row.direction === 'SHORT') return { text: '↓ Vente', tone: 'down' }
  if (gate === 'BUY' || row.direction === 'LONG') return { text: '↑ Achat', tone: 'up' }
  return { text: '— Neutre', tone: '' }
}

function fmtCacheAge(seconds: number): string {
  if (seconds < 5) return 'à l’instant'
  if (seconds < 60) return `il y a ${Math.floor(seconds)}s`
  return `il y a ${Math.floor(seconds / 60)}min`
}

function ReasonChips({ codes, risk }: { codes: string[]; risk?: boolean }) {
  return (
    <div className="chip-row">
      {codes.map((code) => (
        <span key={code} className={`sig-chip${risk ? ' risk-chip' : ''}`} title={code}>
          {labelReason(code)}
        </span>
      ))}
    </div>
  )
}

function AgentBlock({ title, agent }: { title: string; agent: AgentDetail }) {
  return (
    <div className="decision-agent">
      <div className="decision-agent-head">
        <strong>{title}</strong>
        <span className="muted">
          {labelDirection(agent.direction)} · {(agent.confidence * 100).toFixed(0)}%
        </span>
      </div>
      {agent.reasons.length > 0 && <ReasonChips codes={agent.reasons} />}
    </div>
  )
}

function compareRows(a: ScreenerDecisionRow, b: ScreenerDecisionRow, key: SortKey, dir: SortDir): number {
  const mul = dir === 'asc' ? 1 : -1
  switch (key) {
    case 'symbol':
      return mul * a.symbol.localeCompare(b.symbol)
    case 'decision': {
      const ga = rowGate(a)
      const gb = rowGate(b)
      if (ga && gb) return mul * (GATE_RANK[ga] - GATE_RANK[gb])
      if (ga) return mul * 1
      if (gb) return mul * -1
      return mul * (DECISION_RANK[a.decision] - DECISION_RANK[b.decision])
    }
    case 'confidence':
      return mul * (a.confidence - b.confidence)
    case 'ichimoku_score': {
      const av = a.ichimoku_score ?? Number.NEGATIVE_INFINITY
      const bv = b.ichimoku_score ?? Number.NEGATIVE_INFINITY
      return mul * (av - bv)
    }
    case 'rvol': {
      const av = a.rvol ?? Number.NEGATIVE_INFINITY
      const bv = b.rvol ?? Number.NEGATIVE_INFINITY
      return mul * (av - bv)
    }
    case 'price':
      return mul * (a.price - b.price)
    default: {
      const _exhaustive: never = key
      return _exhaustive
    }
  }
}

type PaperConfirmState = {
  symbol: string
  timeframe: string
  intent: OrderIntent | null
  source: 'sheet' | 'matrix'
}

export function DecisionsPage() {
  const [searchParams] = useSearchParams()
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

  const sortKey: SortKey = 'confidence'
  const sortDir: SortDir = 'desc'
  const [symbolQuery, setSymbolQuery] = useState('')
  const [cycleFilter, setCycleFilter] = useState<CycleFilter>('Tous')
  const [timeframe, setTimeframe] = useState('1h')

  const [confirming, setConfirming] = useState(false)
  const [confirmMsg, setConfirmMsg] = useState<string | null>(null)
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
    const filtered = classRows.filter((r) => {
      if (q) {
        const sym = r.symbol.toLowerCase()
        const label = (byId.get(r.symbol)?.label ?? '').toLowerCase()
        const short = sym.replace(/usdt$/, '')
        if (!sym.includes(q) && !short.includes(q) && !label.includes(q)) return false
      }
      if (cycleFilter !== 'Tous' && cycleFromRow(r) !== cycleFilter) return false
      return true
    })
    return [...filtered].sort((a, b) => compareRows(a, b, sortKey, sortDir))
  }, [classRows, symbolQuery, cycleFilter, sortKey, sortDir, byId])

  const highlightRow = useMemo(() => {
    const triggered = visibleRows.filter((r) => cycleFromRow(r) === 'TRIGGERED')
    const pool = triggered.length > 0 ? triggered : visibleRows
    if (pool.length === 0) return null
    return [...pool].sort((a, b) => b.confidence - a.confidence)[0] ?? null
  }, [visibleRows])

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
    if (!fromUrl || selected === fromUrl) return
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

  const activeIntent: OrderIntent | null = intentOverride ?? detail?.order_intent ?? null
  const highlightSym = highlightRow ? instrumentLabel(highlightRow.symbol) : null
  const highlightCycle = highlightRow ? cycleFromRow(highlightRow) : null

  return (
    <div className={`decisions-page${sheetOpen ? ' is-sheet-open' : ''}`}>
      <WorkspacePageHead
        path="/app/opportunites"
        subtitleExtra={pinnedOnly ? ' · Filtre Épinglés actif.' : undefined}
        actions={
          visibleClasses.length > 0 ? (
            <div className="segmented" role="tablist" aria-label="Classe d’actif">
              {pinnedOnly && (
                <Link to="/app/opportunites" className="link">
                  Tout voir
                </Link>
              )}
              {!pinnedOnly && (
                <Link to="/app/opportunites?filter=pinned" className="link">
                  Épinglés
                </Link>
              )}
              {visibleClasses.map((c) => (
                <button
                  key={c}
                  type="button"
                  role="tab"
                  aria-selected={c === marketClass}
                  className={c === marketClass ? 'active' : undefined}
                  onClick={() => selectClass(c)}
                >
                  {CLASS_LABELS[c]}
                </button>
              ))}
              <select
                value={timeframe}
                onChange={(e) => setTimeframe(e.target.value)}
                aria-label="Timeframe"
              >
                <option value="15m">15m</option>
                <option value="1h">1H</option>
                <option value="4h">4H</option>
                <option value="1d">1D</option>
              </select>
              {marketClass !== 'equity' && (
                <button type="button" onClick={() => load(true)} disabled={loading}>
                  {loading ? '…' : 'Actualiser'}
                </button>
              )}
            </div>
          ) : (
            <span className="subtitle">{CLASS_BLURBS[marketClass]}</span>
          )
        }
      />

      {error && (
        <div className="notice" role="alert">
          {error.includes('engine_unreachable') || error.includes('502')
            ? 'Moteur Python injoignable — vérifie que le service tourne (voir ichivol-app/engine/README).'
            : error}
        </div>
      )}

      <div className="toolbar" role="toolbar" aria-label="Filtres opportunités">
        <input
          type="search"
          
          placeholder="Rechercher un actif…"
          value={symbolQuery}
          onChange={(e) => setSymbolQuery(e.target.value)}
          aria-label="Rechercher un actif"
        />
        <div className="segmented" role="tablist" aria-label="Cycle">
          {CYCLE_FILTERS.map((f) => (
            <button
              key={f}
              type="button"
              role="tab"
              aria-selected={cycleFilter === f}
              className={cycleFilter === f ? 'active' : undefined}
              onClick={() => setCycleFilter(f)}
            >
              {f}
            </button>
          ))}
        </div>
        <span className="opp-count">
          {loading && !visibleRows.length
            ? 'scan…'
            : `${visibleRows.length} actifs · clôture ${timeframe.toUpperCase()}`}
          {cacheAge != null ? ` · ${fmtCacheAge(cacheAge)}` : ''}
        </span>
      </div>

      <div className="decisions-split">
        <section className="card decisions-table-panel " aria-label="Matrice de décision">
          <header className="card-head">
            <h2>Matrice de décision</h2>
            <span className="tag gray">5 PORTES</span>
          </header>
          <div className="table-wrap opp-matrix-wrap">
            <table className="data-table opp-matrix" aria-label="Matrice de décision">
              <thead>
                <tr>
                  <th>Actif</th>
                  <th>Direction</th>
                  <th>Participation</th>
                  <th>Structure</th>
                  <th>Emplacement</th>
                  <th>Régime</th>
                  <th>Cycle</th>
                  <th>Confiance</th>
                </tr>
              </thead>
              <tbody>
                {visibleRows.map((row) => {
                  const st = stageStatusesFromRow(row)
                  const cycle = cycleFromRow(row)
                  const dir = directionCell(row)
                  return (
                    <tr
                      key={row.symbol}
                      className={row.symbol === selected ? 'active' : undefined}
                      onClick={() => onSelect(row.symbol)}
                      style={{ cursor: 'pointer' }}
                    >
                      <td>
                        <b>{instrumentLabel(row.symbol)}</b>
                        <small>{row.symbol} · USDT</small>
                      </td>
                      <td className={dir.tone}>{dir.text}</td>
                      {(['participation', 'structure', 'location', 'regime'] as const).map((id) => (
                        <td key={id}>
                          <span className={gateBadgeClass(st[id])}>{gateBadgeLabel(st[id])}</span>
                        </td>
                      ))}
                      <td>
                        <span className={cycleBadgeClass(cycle)}>{cycle}</span>
                      </td>
                      <td className="mono">{(row.confidence * 100).toFixed(0)} %</td>
                    </tr>
                  )
                })}
                {loading && visibleRows.length === 0 && (
                  <tr>
                    <td colSpan={8} className="muted center">
                      Chargement du screener…
                    </td>
                  </tr>
                )}
                {!loading && visibleRows.length === 0 && !error && (
                  <tr>
                    <td colSpan={8} className="muted center">
                      {classRows.length === 0
                        ? marketClass === 'equity'
                          ? 'Aucune action câblée'
                          : 'Aucune ligne — clique Actualiser.'
                        : 'Aucun résultat pour ces filtres'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          {paperMsg && (
            <p className="muted" style={{ padding: '0.5rem 1rem' }}>
              {paperMsg}
            </p>
          )}
        </section>

        {sheetOpen && (
          <aside className="card decision-sheet" aria-label={`Détail ${selected}`}>
            <header className="card-head decision-sheet-head">
              <div>
                <h2>{selected ? instrumentLabel(selected) : ''}</h2>
                <span className="panel-meta">
                  {detailLoading
                    ? byId.get(selected ?? '')?.provider !== 'binance'
                      ? 'calcul… (peut être long)'
                      : 'chargement…'
                    : detail
                      ? `${detail.strategy_version} · ${detail.timeframe}`
                      : ''}
                </span>
              </div>
              <div className="dec-sheet-head-actions">
                {selected && (
                  <Link
                    to={`/app/market?symbol=${encodeURIComponent(selected)}`}
                    className="ghost"
                  >
                    Marché →
                  </Link>
                )}
                <button type="button" className="ghost decision-sheet-close" onClick={closeSheet}>
                  Fermer
                </button>
              </div>
            </header>

            <div className="decision-sheet-scroll">
              {detailError && (
                <div className="notice" role="alert">
                  {detailError}
                </div>
              )}

              {detailLoading && !detail && (
                <p className="muted decision-sheet-loading">
                  Calcul du pipeline en cours
                  {selected && byId.get(selected)?.provider !== 'binance'
                    ? ' — hors crypto ça peut prendre 5–20s (feed + accumulateur).'
                    : '…'}
                </p>
              )}

              {detail && (
                <div className="decision-detail-body">
                  <p className="dec-sheet-summary">{buildDecisionSummary(detail)}</p>

                  <div className="dec-sheet-verdict">
                    <VerdictBadge decision={detail.decision} pipeline={detail.pipeline} />
                    {detail.pipeline?.decision && (
                      <span className="muted">
                        Portes = {labelPipelineGate(detail.pipeline.decision as PipelineGateLabel)} ·
                        Brut = {labelDecision(detail.decision)}
                      </span>
                    )}
                  </div>

                  <section className="dec-before-open" aria-label="Avant d’ouvrir">
                    <h3 className="subhead">Avant d’ouvrir (paper)</h3>
                    <TradePlanCard intent={activeIntent} pipelineView={pipelineView} />
                    <ProposePaperTradePanel
                      intent={activeIntent}
                      loading={intentLoading || detailLoading}
                      confirming={paperConfirming}
                      onConfirm={() => void onConfirmPaperOrder()}
                      onRefresh={() => void onRefreshIntent()}
                    />
                  </section>

                  <div className="decision-confirm-row dec-secondary-actions">
                    <button
                      type="button"
                      className="ghost"
                      disabled={confirming}
                      onClick={() => void onConfirmDetail()}
                    >
                      {confirming ? 'Enregistrement…' : 'Journal seulement'}
                    </button>
                    <button
                      type="button"
                      className="ghost"
                      onClick={() => explainDecision(decisionPayloadFromDetail(detail))}
                      title="Ouvre le Copilot avec un prompt déjà prêt"
                    >
                      Expliquer
                    </button>
                    <button
                      type="button"
                      className="ghost"
                      onClick={() => compareGates(decisionPayloadFromDetail(detail))}
                      title="Écart badge Brut vs verdict Portes"
                    >
                      Écart Portes / Brut
                    </button>
                    <span className="muted">
                      Paper = position virtuelle (CTA ci-dessus) · Journal = snapshot local.
                    </span>
                    {confirmMsg?.startsWith('ok') ? (
                      <span className="panel-meta">
                        Enregistré{confirmMsg.slice(2)} ·{' '}
                        <Link to="/app/journal">journal</Link>
                        {' · '}
                        <Link to="/app/portefeuille">synthèse</Link>
                        {' · '}
                        <Link to="/app/portefeuille?tab=positions">paper</Link>
                      </span>
                    ) : (
                      confirmMsg && <span className="panel-meta">{confirmMsg}</span>
                    )}
                  </div>

                  {pipelineView && (
                    <details className="decision-agents-details" open>
                      <summary className="subhead">Pipeline (5 portes)</summary>
                      <DecisionPipelinePanel view={pipelineView} />
                    </details>
                  )}

                  <details className="decision-agents-details">
                    <summary className="subhead">Evidence &amp; preuves</summary>
                    <SignalEvidenceCard detail={detail} />
                  </details>

                  <details className="decision-agents-details">
                    <summary className="subhead">Agents bruts (Ichimoku / RVOL)</summary>
                    <div className="decision-agents">
                      <AgentBlock title="Ichimoku" agent={detail.ichimoku} />
                      <AgentBlock title="RVOL" agent={detail.rvol_detail} />
                    </div>
                  </details>
                </div>
              )}
            </div>
          </aside>
        )}
      </div>

      <div className="grid " style={{ marginTop: '1.25rem' }}>
        <section className="card" aria-label="De l’observation à la décision">
          <header className="card-head">
            <h2>De l’observation à la décision</h2>
          </header>
          <div className="card-body">
            <div className="toolbar">
              {FLOW_STAGES.map((s, i) => (
                <span key={s} className="toolbar">
                  {i > 0 && <span className="">→</span>}
                  <span
                    className={
                      s === 'REFUSÉ'
                        ? 'tag red'
                        : s === 'TRIGGERED' || s === 'ACCEPTÉ'
                          ? 'tag amber'
                          : s === 'ARMED'
                            ? 'tag green'
                            : 'iv-badge'
                    }
                  >
                    {s}
                  </span>
                </span>
              ))}
            </div>
            <p className="muted" style={{ margin: 0, fontSize: '0.75rem', lineHeight: 1.5 }}>
              Un signal traverse chaque contrôle. La confiance complète la lecture ; elle ne
              remplace jamais le verdict du Risk Kernel.
            </p>
          </div>
        </section>

        <section className="card opp-why" aria-label="Pourquoi cet actif">
          <header className="card-head">
            <h2>{highlightSym ? `Pourquoi ${highlightSym} ?` : 'Pourquoi ?'}</h2>
            {highlightCycle && (
              <span className={cycleBadgeClass(highlightCycle)}>{highlightCycle}</span>
            )}
          </header>
          <div className="card-body">
            {highlightRow ? (
              <>
                <p>
                  {cycleFromRow(highlightRow) === 'TRIGGERED'
                    ? 'Direction, volume et structure convergent. Le plan attend une validation finale du risque.'
                    : cycleFromRow(highlightRow) === 'ARMED'
                      ? 'Direction favorable ; participation à confirmer sur bougie clôturée.'
                      : 'Sous surveillance — les portes n’autorisent pas encore une action.'}{' '}
                  Confiance {(highlightRow.confidence * 100).toFixed(0)} %.
                </p>
                <button
                  type="button"
                  className="primary"
                  onClick={() => onSelect(highlightRow.symbol)}
                >
                  Ouvrir la fiche de décision →
                </button>
              </>
            ) : (
              <p className="muted">Aucun actif à mettre en avant pour ce filtre.</p>
            )}
          </div>
        </section>
      </div>

      {paperConfirm && (
        <PaperConfirmSheet
          symbol={paperConfirm.symbol}
          timeframe={paperConfirm.timeframe}
          symbolLabel={instrumentLabel(paperConfirm.symbol)}
          intent={paperConfirm.intent}
          confirming={paperConfirming}
          error={paperConfirmError}
          onConfirm={(order) => void executePaperConfirm(order)}
          onCancel={() => {
            if (!paperConfirming) setPaperConfirm(null)
          }}
        />
      )}
    </div>
  )
}
