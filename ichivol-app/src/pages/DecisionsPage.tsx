import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { DecisionPipelinePanel } from '../components/DecisionPipelinePanel'
import { GateMatrix } from '../components/GateMatrix'
import { ProposePaperTradePanel } from '../components/ProposePaperTradePanel'
import { SignalEvidenceCard } from '../components/SignalEvidenceCard'
import { VerdictBadge } from '../components/VerdictBadge'
import { labelDecision, labelDirection, labelReason } from '../lib/decisionLabels'
import { TradePlanCard } from '../components/TradePlanCard'
import { pipelineFromDecisionDetail } from '../lib/decisionPipeline'
import {
  getDecisionDetail,
  getScreener,
  type AgentDetail,
  type DecisionDetail,
  type DecisionLabel,
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
import { openPaperPosition, proposePaperTrade, type OrderIntent } from '../lib/paper'
import { decisionPayloadFromDetail } from '../lib/agent'
import { useCopilotNav } from '../lib/useCopilotNav'

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
    case 'decision':
      return mul * (DECISION_RANK[a.decision] - DECISION_RANK[b.decision])
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

  const [confirming, setConfirming] = useState(false)
  const [confirmMsg, setConfirmMsg] = useState<string | null>(null)
  const [listView, setListView] = useState<ListView>('liste')
  const [paperBusySymbol, setPaperBusySymbol] = useState<string | null>(null)
  const [paperMsg, setPaperMsg] = useState<string | null>(null)
  const [paperConfirming, setPaperConfirming] = useState(false)
  const [intentOverride, setIntentOverride] = useState<OrderIntent | null>(null)
  const [intentLoading, setIntentLoading] = useState(false)
  const { explainDecision, compareGates } = useCopilotNav()

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
      if (minR != null && Number.isFinite(minR)) {
        if (r.rvol == null || r.rvol < minR) return false
      }
      return true
    })
    return [...filtered].sort((a, b) => compareRows(a, b, sortKey, sortDir))
  }, [classRows, symbolQuery, decisionFilter, rvolMin, sortKey, sortDir, byId])

  function instrumentLabel(id: string): string {
    return byId.get(id)?.label ?? id.replace(/USDT$/i, '')
  }

  function load(force = false) {
    setLoading(true)
    setError(null)
    getScreener('1h', force)
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

  useEffect(() => load(), [])

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
    if (!detail) return
    setPaperConfirming(true)
    setConfirmMsg(null)
    try {
      await confirmUserDecision({
        symbol: detail.symbol,
        interval: detail.timeframe,
        bias: detail.direction,
        rvol: detail.rvol ?? 0,
        signalKind: detail.decision,
        gateDecision: detail.pipeline?.decision,
        confidence: detail.confidence,
      })
      const pos = await openPaperPosition(detail.symbol, detail.timeframe)
      setConfirmMsg(
        `ok · paper ${pos.direction} qty ${pos.qty != null ? pos.qty.toPrecision(4) : '—'}`,
      )
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Échec paper'
      setConfirmMsg(msg.includes('not_actionable') ? 'paper skip (WATCH/NO_TRADE)' : msg)
    } finally {
      setPaperConfirming(false)
    }
  }

  async function onRefreshIntent() {
    if (!detail) return
    setIntentLoading(true)
    try {
      setIntentOverride(await proposePaperTrade(detail.symbol, detail.timeframe))
    } catch {
      setIntentOverride(null)
    } finally {
      setIntentLoading(false)
    }
  }

  async function onOpenPaperFromMatrix(row: ScreenerDecisionRow) {
    setPaperBusySymbol(row.symbol)
    setPaperMsg(null)
    try {
      const pos = await openPaperPosition(row.symbol, row.timeframe || '1h')
      setPaperMsg(`${pos.symbol} · paper ${pos.direction} @ ${pos.entry_price}`)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Échec paper'
      setPaperMsg(msg.includes('not_actionable') ? `${row.symbol} · pas actionable (Portes)` : msg)
    } finally {
      setPaperBusySymbol(null)
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
    setSelected(symbol)
    setDetail(null)
    setDetailError(null)
    setDetailLoading(true)
    setIntentOverride(null)
    setConfirmMsg(null)
    getDecisionDetail(symbol)
      .then(setDetail)
      .catch((err: unknown) =>
        setDetailError(err instanceof Error ? err.message : 'Erreur de chargement'),
      )
      .finally(() => setDetailLoading(false))
  }

  useEffect(() => {
    const fromNotif = searchParams.get('symbol')
    if (!fromNotif || selected === fromNotif) return
    setSelected(fromNotif)
    setDetail(null)
    setDetailError(null)
    setDetailLoading(true)
    setIntentOverride(null)
    setConfirmMsg(null)
    getDecisionDetail(fromNotif)
      .then(setDetail)
      .catch((err: unknown) =>
        setDetailError(err instanceof Error ? err.message : 'Erreur de chargement'),
      )
      .finally(() => setDetailLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps -- deep-link once per symbol query
  }, [searchParams])

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

  return (
    <div className={`decisions-page${sheetOpen ? ' is-sheet-open' : ''}`}>
      <header className="page-head market-head">
        <div className="market-head-copy">
          <h1>Décisions</h1>
          <p className="muted">
            Pipeline Direction → Participation → Structure → Location → Régime. Vue{' '}
            <strong>Liste</strong> ou <strong>Matrice</strong> (pastilles par porte) — clic = détail
            à droite.
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
            {(symbolQuery || decisionFilter !== 'all' || rvolMin) && (
              <button
                type="button"
                className="ghost decisions-filter-reset"
                onClick={() => {
                  setSymbolQuery('')
                  setDecisionFilter('all')
                  setRvolMin('')
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
                        title="Tri sur le combiner legacy ; le badge affiché = Portes (pipeline) si dispo"
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
              <button type="button" className="ghost decision-sheet-close" onClick={closeSheet}>
                Fermer
              </button>
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
                  <SignalEvidenceCard detail={detail} />

                  <TradePlanCard intent={activeIntent} pipelineView={pipelineView} />

                  <ProposePaperTradePanel
                    intent={activeIntent}
                    loading={intentLoading || detailLoading}
                    confirming={paperConfirming}
                    onConfirm={() => void onConfirmPaperOrder()}
                    onRefresh={() => void onRefreshIntent()}
                  />

                  <div className="decision-confirm-row">
                    <button
                      type="button"
                      className="ghost"
                      disabled={confirming}
                      onClick={() => void onConfirmDetail()}
                    >
                      {confirming ? 'Enregistrement…' : 'Confirmer dans le journal'}
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
                      title="Écart badge combiner vs verdict portes"
                    >
                      Écart portes
                    </button>
                    <span className="muted">
                      Journal ≠ paper — snapshot local seulement.
                    </span>
                    {confirmMsg?.startsWith('ok') ? (
                      <span className="panel-meta">
                        Enregistré{confirmMsg.slice(2)} ·{' '}
                        <Link to="/app/journal">journal</Link>
                        {' · '}
                        <Link to="/app/paper">paper</Link>
                      </span>
                    ) : (
                      confirmMsg && <span className="panel-meta">{confirmMsg}</span>
                    )}
                  </div>

                  {pipelineView && <DecisionPipelinePanel view={pipelineView} />}

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
    </div>
  )
}
