import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { DecisionPipelinePanel } from '../components/DecisionPipelinePanel'
import { GateMatrix } from '../components/GateMatrix'
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
  PIPELINE_STAGE_ORDER,
  pipelineFromDecisionDetail,
  stageFullLabel,
  stageMatrixLabel,
  stageStatusesFromRow,
  type PipelineStageId,
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
import { confirmUserDecision, patchUserDecisionStatus } from '../lib/userDecisions'
import {
  getPaperOverview,
  listPaperPositions,
  openPaperPosition,
  proposePaperTrade,
  type OrderIntent,
} from '../lib/paper'
import { decisionPayloadFromDetail } from '../lib/agent'
import { useCopilotNav } from '../lib/useCopilotNav'
import './DecisionsPage.css'

type SortKey = 'symbol' | 'decision' | 'confidence' | 'ichimoku_score' | 'rvol' | 'price'
type SortDir = 'asc' | 'desc'
type ListView = 'liste' | 'matrice'

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

const DECISION_FILTERS: Array<'all' | DecisionLabel> = [
  'all',
  'STRONG_BUY',
  'BUY',
  'WATCH',
  'WAIT',
  'SELL',
  'STRONG_SELL',
]

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

function sortMarker(active: boolean, dir: SortDir): string {
  if (!active) return ''
  return dir === 'asc' ? ' ↑' : ' ↓'
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

function MethodBanner({ rows }: { rows: ScreenerDecisionRow[] }) {
  const counts = useMemo(() => {
    const byStage: Record<PipelineStageId, Record<PipelineStageStatus, number>> = {
      direction: { pass: 0, fail: 0, watch: 0, pending: 0, skip: 0 },
      participation: { pass: 0, fail: 0, watch: 0, pending: 0, skip: 0 },
      structure: { pass: 0, fail: 0, watch: 0, pending: 0, skip: 0 },
      location: { pass: 0, fail: 0, watch: 0, pending: 0, skip: 0 },
      regime: { pass: 0, fail: 0, watch: 0, pending: 0, skip: 0 },
    }
    for (const row of rows) {
      const st = stageStatusesFromRow(row)
      for (const id of PIPELINE_STAGE_ORDER) {
        byStage[id][st[id]] += 1
      }
    }
    return byStage
  }, [rows])

  return (
    <section className="panel dec-method" aria-label="Méthode">
      <p className="dec-method-lead">
        Cinq portes successives. Seules <strong>Achat</strong> / <strong>Vente</strong> (colonne
        Portes) autorisent un ordre paper. <strong>Brut</strong> = Ichimoku + RVOL seul — diagnostic,
        pas un verdict d’action.
      </p>
      <ol className="dec-method-steps">
        {PIPELINE_STAGE_ORDER.map((id) => {
          const c = counts[id]
          const ok = c.pass
          const blocked = c.fail
          const soft = c.watch + c.pending
          return (
            <li key={id} title={stageFullLabel(id)}>
              <span className="dec-method-n">{stageMatrixLabel(id)}</span>
              <strong>{stageFullLabel(id)}</strong>
              <span className="muted dec-method-counts">
                <span className="up">{ok} ok</span>
                {' · '}
                <span className="down">{blocked} bloqué</span>
                {soft > 0 ? ` · ${soft} prudence` : ''}
              </span>
            </li>
          )
        })}
      </ol>
    </section>
  )
}

type PaperConfirmState = {
  symbol: string
  timeframe: string
  intent: OrderIntent
  source: 'sheet' | 'matrix'
}

export function DecisionsPage() {
  const [searchParams] = useSearchParams()
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
  const [rvolMin, setRvolMin] = useState('')
  const [actionableOnly, setActionableOnly] = useState(false)
  const [timeframe, setTimeframe] = useState('1h')

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
    if (marketClass === 'equity') {
      return instruments
        .filter((i) => i.asset_class === 'equity' && i.wired)
        .map((i) => {
          const hit = rows.find((r) => r.symbol === i.id)
          return hit ?? placeholderRow(i)
        })
    }
    return rows.filter((r) => byId.get(r.symbol)?.asset_class === marketClass)
  }, [marketClass, instruments, rows, byId])

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
  }, [classRows, symbolQuery, decisionFilter, rvolMin, actionableOnly, sortKey, sortDir, byId])

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
    if (!detail || !intent) return
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

  async function executePaperConfirm() {
    if (!paperConfirm || paperConfirmLock.current) return
    paperConfirmLock.current = true
    setPaperConfirming(true)
    setConfirmMsg(null)
    setPaperMsg(null)
    setPaperConfirmError(null)
    try {
      const sameDetail = detail?.symbol === paperConfirm.symbol ? detail : null
      const gate = paperConfirm.intent.pipeline_decision
      const journalRow = await confirmUserDecision({
        symbol: paperConfirm.symbol,
        interval: paperConfirm.timeframe,
        bias: paperConfirm.intent.direction === 'SHORT' ? 'BEARISH' : 'BULLISH',
        rvol: sameDetail?.rvol ?? 0,
        signalKind:
          sameDetail?.decision ??
          (gate === 'SELL' ? 'SELL' : gate === 'BUY' ? 'BUY' : 'WATCH'),
        gateDecision: gate,
        confidence: sameDetail?.confidence,
      })
      let pos: Awaited<ReturnType<typeof openPaperPosition>>
      try {
        pos = await openPaperPosition(paperConfirm.symbol, paperConfirm.timeframe)
      } catch (openErr) {
        // Pas de décision « confirmée » orpheline : si le moteur refuse l'ouverture,
        // on écarte l'entrée de journal qu'on vient de créer (sauf si elle existait déjà).
        if (!journalRow.deduped) {
          await patchUserDecisionStatus(journalRow.id, 'dismissed').catch(() => undefined)
        }
        throw openErr
      }
      const already = pos.already_open === true || pos.created === false
      const msg = already
        ? `déjà ouvert · ${pos.symbol} ${pos.direction} (pas de 2ᵉ notional)`
        : `ok · paper ${pos.direction} qty ${pos.qty != null ? pos.qty.toPrecision(4) : '—'}`
      setConfirmMsg(msg)
      setPaperMsg(
        already
          ? `${pos.symbol} · déjà en portefeuille — achat verrouillé`
          : `${pos.symbol} · paper ${pos.direction} @ ${pos.entry_price}`,
      )
      setOpenPaperSymbols((prev) => new Set([...prev, pos.symbol]))
      setPaperConfirm(null)
      void refreshOpenPaperSymbols()
    } catch (err: unknown) {
      const raw = err instanceof Error ? err.message : 'Échec paper'
      const stale = raw.includes('not_actionable')
      const msg = stale
        ? 'La décision est repassée à Attente/Pas de trade depuis l’affichage (bougie en formation). Aucune position ouverte.'
        : raw
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
      const intent = await proposePaperTrade(row.symbol, row.timeframe || timeframe)
      setPaperConfirm({
        symbol: row.symbol,
        timeframe: row.timeframe || timeframe,
        intent,
        source: 'matrix',
      })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Échec paper'
      setPaperMsg(msg.includes('not_actionable') ? `${row.symbol} · pas actionable (Portes)` : msg)
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

  return (
    <div className={`decisions-page${sheetOpen ? ' is-sheet-open' : ''}`}>
      <header className="page-head market-head">
        <div className="market-head-copy">
          <h1>Décisions</h1>
          <p className="muted">
            Filtre actionnable · comprendre les portes · confirmer paper. Vue Liste ou Matrice —
            clic = détail.
          </p>
          <p className="muted">{CLASS_BLURBS[marketClass]}</p>
        </div>
        {visibleClasses.length > 0 && (
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
        )}
      </header>

      <MethodBanner rows={classRows} />

      <section className="dec-gate-stats" aria-label="Résumé Portes">
        <button
          type="button"
          className="panel overview-stat overview-stat--bull"
          onClick={() => {
            setActionableOnly(true)
            setDecisionFilter('all')
          }}
          title="Filtrer les actionnables Achat"
        >
          <span className="overview-stat-label muted">Achats (Portes)</span>
          <strong className="mono">{loading && !classRows.length ? '—' : gateStats.buy}</strong>
        </button>
        <button
          type="button"
          className="panel overview-stat overview-stat--bear"
          onClick={() => {
            setActionableOnly(true)
            setDecisionFilter('all')
          }}
          title="Filtrer les actionnables Vente"
        >
          <span className="overview-stat-label muted">Ventes (Portes)</span>
          <strong className="mono">{loading && !classRows.length ? '—' : gateStats.sell}</strong>
        </button>
        <button
          type="button"
          className="panel overview-stat"
          onClick={() => {
            setActionableOnly(false)
            setDecisionFilter('all')
          }}
        >
          <span className="overview-stat-label muted">Surveillance</span>
          <strong className="mono">{loading && !classRows.length ? '—' : gateStats.watch}</strong>
        </button>
        <div className="panel overview-stat">
          <span className="overview-stat-label muted">Scannées · {timeframe}</span>
          <strong className="mono">{loading && !classRows.length ? '—' : gateStats.total}</strong>
          <span className="overview-stat-meta muted">
            {gateStats.buy + gateStats.sell} actionnables
          </span>
        </div>
      </section>

      {error && (
        <div className="banner error" role="alert">
          {error.includes('engine_unreachable') || error.includes('502')
            ? 'Moteur Python injoignable — vérifie que le service tourne (voir ichivol-app/engine/README).'
            : error}
        </div>
      )}

      <div className="decisions-split">
        <section className="panel decisions-table-panel">
          <header className="panel-head">
            <h2>Screener · {CLASS_LABELS[marketClass]}</h2>
            <div className="panel-head-actions">
              <div className="decisions-view-tabs" role="tablist" aria-label="Vue screener">
                <button
                  type="button"
                  role="tab"
                  aria-selected={listView === 'liste'}
                  className={listView === 'liste' ? 'is-active' : undefined}
                  onClick={() => setListView('liste')}
                >
                  Liste
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={listView === 'matrice'}
                  className={listView === 'matrice' ? 'is-active' : undefined}
                  onClick={() => setListView('matrice')}
                >
                  Matrice
                </button>
              </div>
              <span className="panel-meta">
                {loading
                  ? 'scan…'
                  : marketClass === 'equity'
                    ? `${visibleRows.length} · détail au clic (pas de scan masse)`
                    : `${visibleRows.length}/${classRows.length}${cacheAge != null ? ` · ${fmtCacheAge(cacheAge)}` : ''}`}
              </span>
              {marketClass !== 'equity' && (
                <button type="button" className="ghost" onClick={() => load(true)} disabled={loading}>
                  Rafraîchir
                </button>
              )}
            </div>
          </header>

          <div className="decisions-filters" role="search">
            <label className="decisions-filter">
              <span className="muted">TF</span>
              <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)}>
                <option value="15m">15m</option>
                <option value="1h">1h</option>
                <option value="4h">4h</option>
                <option value="1d">1d</option>
              </select>
            </label>
            <label className="decisions-filter">
              <span className="muted">Symbole</span>
              <input
                type="search"
                value={symbolQuery}
                onChange={(e) => setSymbolQuery(e.target.value)}
                placeholder="BTC, EUR, XAU…"
                autoComplete="off"
              />
            </label>
            <label className="decisions-filter">
              <span className="muted">Décision</span>
              <select
                value={decisionFilter}
                onChange={(e) => setDecisionFilter(e.target.value as 'all' | DecisionLabel)}
              >
                {DECISION_FILTERS.map((d) => (
                  <option key={d} value={d}>
                    {d === 'all' ? 'Toutes' : labelDecision(d)}
                  </option>
                ))}
              </select>
            </label>
            <label className="decisions-filter">
              <span className="muted">RVOL ≥</span>
              <input
                type="number"
                min={0}
                step={0.1}
                value={rvolMin}
                onChange={(e) => setRvolMin(e.target.value)}
                placeholder="ex. 1.5"
              />
            </label>
            <label className="decisions-filter dec-filter-check">
              <input
                type="checkbox"
                checked={actionableOnly}
                onChange={(e) => setActionableOnly(e.target.checked)}
              />
              <span className="muted">Actionnables (Portes Achat/Vente)</span>
            </label>
            {(symbolQuery || decisionFilter !== 'all' || rvolMin || actionableOnly) && (
              <button
                type="button"
                className="ghost decisions-filter-reset"
                onClick={() => {
                  setSymbolQuery('')
                  setDecisionFilter('all')
                  setRvolMin('')
                  setActionableOnly(false)
                }}
              >
                Reset
              </button>
            )}
          </div>

          <div className="table-wrap">
            {listView === 'matrice' ? (
              loading && visibleRows.length === 0 ? (
                <p className="muted center">Chargement du screener…</p>
              ) : (
                <>
                  <GateMatrix
                    rows={visibleRows}
                    selected={selected}
                    onSelect={onSelect}
                    symbolLabel={instrumentLabel}
                    onOpenPaper={onOpenPaperFromMatrix}
                    paperBusySymbol={paperBusySymbol}
                    openPaperSymbols={openPaperSymbols}
                    emptyHint={
                      classRows.length === 0
                        ? marketClass === 'equity'
                          ? 'Aucune action câblée'
                          : 'Aucune ligne pour cette classe — clique Rafraîchir.'
                        : 'Aucun résultat pour ces filtres'
                    }
                  />
                  {paperMsg && <p className="muted decisions-paper-msg">{paperMsg}</p>}
                </>
              )
            ) : (
              <table className="decisions-table">
                <thead>
                  <tr>
                    <th>
                      <button type="button" className="th-sort" onClick={() => toggleSort('symbol')}>
                        Symbole{sortMarker(sortKey === 'symbol', sortDir)}
                      </button>
                    </th>
                    <th>
                      <button
                        type="button"
                        className="th-sort"
                        onClick={() => toggleSort('decision')}
                        title="Tri sur le verdict Portes (pipeline) ; Brut = diagnostic Ichi+RVOL"
                      >
                        Portes{sortMarker(sortKey === 'decision', sortDir)}
                      </button>
                    </th>
                    {!sheetOpen && (
                      <th>
                        <button
                          type="button"
                          className="th-sort"
                          onClick={() => toggleSort('confidence')}
                        >
                          Confiance{sortMarker(sortKey === 'confidence', sortDir)}
                        </button>
                      </th>
                    )}
                    {!sheetOpen && (
                      <th>
                        <button
                          type="button"
                          className="th-sort"
                          onClick={() => toggleSort('ichimoku_score')}
                        >
                          Ichimoku{sortMarker(sortKey === 'ichimoku_score', sortDir)}
                        </button>
                      </th>
                    )}
                    <th>
                      <button type="button" className="th-sort" onClick={() => toggleSort('rvol')}>
                        RVOL{sortMarker(sortKey === 'rvol', sortDir)}
                      </button>
                    </th>
                    {!sheetOpen && (
                      <th>
                        <button
                          type="button"
                          className="th-sort"
                          onClick={() => toggleSort('price')}
                        >
                          Prix{sortMarker(sortKey === 'price', sortDir)}
                        </button>
                      </th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {visibleRows.map((r) => (
                    <tr
                      key={r.symbol}
                      className={r.symbol === selected ? 'is-active' : undefined}
                      onClick={() => onSelect(r.symbol)}
                    >
                      <td>
                        <strong title={r.symbol}>{instrumentLabel(r.symbol)}</strong>
                      </td>
                      <td>
                        <VerdictBadge decision={r.decision} pipeline={r.pipeline} />
                      </td>
                      {!sheetOpen && <td className="mono">{(r.confidence * 100).toFixed(0)}%</td>}
                      {!sheetOpen && (
                        <td className="mono">
                          {r.ichimoku_score != null ? r.ichimoku_score.toFixed(0) : '—'}
                        </td>
                      )}
                      <td className="mono">{r.rvol != null ? `${r.rvol.toFixed(2)}×` : '—'}</td>
                      {!sheetOpen && (
                        <td className="mono">
                          {r.price > 0 ? r.price.toFixed(r.price >= 100 ? 2 : 4) : '—'}
                        </td>
                      )}
                    </tr>
                  ))}
                  {loading && visibleRows.length === 0 && (
                    <tr>
                      <td colSpan={colCount} className="muted center">
                        Chargement du screener…
                      </td>
                    </tr>
                  )}
                  {!loading && visibleRows.length === 0 && !error && (
                    <tr>
                      <td colSpan={colCount} className="muted center">
                        {classRows.length === 0
                          ? marketClass === 'equity'
                            ? 'Aucune action câblée'
                            : 'Aucune ligne pour cette classe — clique Rafraîchir (le cache se reconstruit après un redémarrage moteur).'
                          : 'Aucun résultat pour ces filtres'}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            )}
          </div>
        </section>

        {sheetOpen && (
          <aside className="panel decision-sheet" aria-label={`Détail ${selected}`}>
            <header className="panel-head decision-sheet-head">
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
                <div className="banner error" role="alert">
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
                        <Link to="/app/synthese">synthèse</Link>
                        {' · '}
                        <Link to="/app/paper">paper</Link>
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

      {paperConfirm && (
        <PaperConfirmSheet
          symbolLabel={instrumentLabel(paperConfirm.symbol)}
          intent={paperConfirm.intent}
          confirming={paperConfirming}
          error={paperConfirmError}
          onConfirm={() => void executePaperConfirm()}
          onCancel={() => {
            if (!paperConfirming) setPaperConfirm(null)
          }}
        />
      )}
    </div>
  )
}
