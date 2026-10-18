/**
 * Opportunités — port littéral de design-reference/ichivol-workspace `opportunites()` + page-head.
 * Classes HTML = maquette. Données = engine (pas de démo inventée ; manquant → « — »).
 * Paper : fiche dialog → aperçu (PaperConfirmSheet / previewPaperBuy) → openPaperPosition.
 */

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { DecisionPipelinePanel } from '../components/DecisionPipelinePanel'
import { MtfPanel } from '../components/MtfPanel'
import { ChartIntelligencePanel } from '../components/chart-intelligence'
import { PaperConfirmSheet } from '../components/PaperConfirmSheet'
import { BASELINE_PORTFOLIO_CODE, SESSIONS_CODE } from '../lib/rsPortfolio'
import { loadAllBooks } from '../lib/allBooks'
import { SignalEvidenceCard } from '../components/SignalEvidenceCard'
import '../components/engineEvidence.css'
import {
  getDecisionDetail,
  getScreener,
  type DecisionDetail,
  type ScreenerDecisionRow,
} from '../lib/decisions'
import { pipelineFromDecisionDetail } from '../lib/decisionPipeline'
import { buildDecisionSummary } from '../lib/decisionLabels'
import { labelEngineCode } from '../lib/engineTerminology'
import { displaySymbol } from '../lib/markets'
import { toEngineSymbol } from '../lib/engineSymbol'
import {
  listPaperPositions,
  openPaperPosition,
  proposePaperTrade,
  type ManualOrderInput,
  type OrderIntent,
} from '../lib/paper'
import { confirmUserDecision } from '../lib/userDecisions'
import { VpValidationBadge } from '../components/VpValidationBadge'
import { isActionableBuySell, VP_VALIDATION_BADGE_LABEL } from '../lib/vpValidationCopy'
import {
  maquetteGateBadge,
  type MaquetteBadgeTone,
} from './market/marketMaquetteHelpers'
import { EVE_ACTION_FR } from '../lib/eveDecisions'
import {
  eveActionTone,
  jevHealthTone,
  latestDossierBySymbol,
  overlayFromDossier,
  type EveDossierLite,
} from '../lib/eveMatrix'
import './DecisionsPage.css'

type OppFilter = 'Tous' | 'WATCH' | 'ARMED' | 'TRIGGERED'

type CycleLabel = 'WATCH' | 'ARMED' | 'TRIGGERED' | 'ACCEPTÉ' | 'REFUSÉ' | '—'

const CYCLE_FR: Record<CycleLabel, string> = {
  WATCH: 'Veille',
  ARMED: 'Armé',
  TRIGGERED: 'Déclenché',
  ACCEPTÉ: 'Accepté',
  REFUSÉ: 'Refusé',
  '—': '—',
}

const FILTER_FR: Record<OppFilter, string> = {
  Tous: 'Tous',
  WATCH: 'Veille',
  ARMED: 'Armé',
  TRIGGERED: 'Déclenché',
}

type PaperConfirmState = {
  symbol: string
  timeframe: string
  intent: OrderIntent | null
  defaultPortfolio: string
  /** Fiche au moment de l'ouverture du ticket : la fiche se ferme pour laisser le ticket au premier plan. */
  detail: DecisionDetail | null
}

type Tone = MaquetteBadgeTone | 'buy' | 'sell' | 'cyan'

const TONE_CLASS: Record<Tone, string> = {
  green: 'is-mint',
  amber: 'is-amber',
  red: 'is-sell',
  gray: 'is-muted',
  buy: 'is-buy',
  sell: 'is-sell',
  cyan: 'is-cyan',
  '': 'is-cyan',
}

function badge(text: string, tone: Tone | string = ''): ReactNode {
  let inferred = tone
  if (!inferred) {
    inferred = /PASSE|ACCEPTÉ|OUVERTE|VALIDÉ/i.test(text)
      ? 'green'
      : /REFUS|BLOQU|ERREUR|ÉCHEC/i.test(text)
        ? 'red'
        : /PRUDENCE|ARMÉ|ARME/i.test(text)
          ? 'amber'
          : /VEILLE/i.test(text)
            ? 'gray'
            : ''
  }
  return <span className={`iv-tag ${TONE_CLASS[inferred as Tone] ?? 'is-cyan'}`}>{text}</span>
}

function cycleFromRow(row: ScreenerDecisionRow): CycleLabel {
  const gate = row.pipeline?.decision?.toUpperCase?.() ?? ''
  if (gate === 'BUY' || gate === 'SELL') return 'TRIGGERED'
  if (gate === 'WATCH') return 'ARMED'
  if (gate === 'NO_TRADE') return 'WATCH'
  const d = String(row.decision || '').toUpperCase()
  if (d === 'STRONG_BUY' || d === 'STRONG_SELL' || d === 'BUY' || d === 'SELL') return 'TRIGGERED'
  if (d === 'WATCH') return 'ARMED'
  if (d === 'WAIT') return 'WATCH'
  return '—'
}

const CYCLE_TONE: Record<CycleLabel, Tone> = {
  WATCH: 'gray',
  ARMED: 'amber',
  TRIGGERED: 'cyan',
  ACCEPTÉ: 'green',
  REFUSÉ: 'red',
  '—': 'gray',
}

function cycleTag(cycle: CycleLabel): ReactNode {
  return badge(CYCLE_FR[cycle], CYCLE_TONE[cycle])
}

/** Action d'Ève en français ; achat en bleu, vente à découvert en rouge. */
function eveTag(action: string): ReactNode {
  const a = action.toUpperCase()
  const text = EVE_ACTION_FR[a] ?? action
  const tone = eveActionTone(a)
  return badge(text, a === 'LONG' ? 'buy' : a === 'SHORT' ? 'sell' : tone || 'gray')
}

type GateStageId = 'direction' | 'participation' | 'structure' | 'location' | 'regime'
type GateStatus = 'pass' | 'fail' | 'watch' | 'pending' | 'skip'

const GATES: { id: GateStageId; short: string; label: string }[] = [
  { id: 'direction', short: 'D', label: 'Direction' },
  { id: 'participation', short: 'P', label: 'Participation' },
  { id: 'structure', short: 'S', label: 'Structure' },
  { id: 'location', short: 'E', label: 'Emplacement' },
  { id: 'regime', short: 'R', label: 'Régime' },
]

const GATE_GLYPH: Record<GateStatus, string> = {
  pass: '✓',
  watch: '~',
  fail: '✕',
  pending: '·',
  skip: '·',
}

/** Statut d'une porte ; la participation retombe sur le RVOL si le pipeline ne la donne pas. */
function gateStatus(row: ScreenerDecisionRow, stageId: GateStageId): GateStatus | null {
  const st = row.pipeline?.stages?.find((s) => s.id === stageId)
  if (st) return st.status
  if (stageId === 'participation' && row.rvol != null && Number.isFinite(row.rvol)) {
    return row.rvol >= 1.5 ? 'pass' : 'watch'
  }
  return null
}

function gateText(status: GateStatus | null): string {
  const b = maquetteGateBadge(status)
  // La matrice dit BLOQUÉ plutôt qu'ÉCHEC
  return b.text === 'ÉCHEC' ? 'BLOQUÉ' : b.text
}

function GatePip({ row, gate }: { row: ScreenerDecisionRow; gate: (typeof GATES)[number] }) {
  const status = gateStatus(row, gate.id)
  const text = gateText(status)
  return (
    <span className={`opps-gate is-${status ?? 'none'}`} title={`${gate.label} · ${text}`} aria-label={`${gate.label} : ${text}`}>
      {status ? GATE_GLYPH[status] : '·'}
    </span>
  )
}

function directionCell(row: ScreenerDecisionRow): ReactNode {
  const gate = row.pipeline?.decision
  const showVp = isActionableBuySell(gate) || isActionableBuySell(row.decision)
  if (row.direction === 'SHORT' || row.decision === 'SELL' || row.decision === 'STRONG_SELL') {
    return (
      <span className="opps-dir down">
        Vente
        {showVp ? <VpValidationBadge compact /> : null}
      </span>
    )
  }
  if (row.direction === 'LONG' || row.decision === 'BUY' || row.decision === 'STRONG_BUY') {
    return (
      <span className="opps-dir up">
        Achat
        {showVp ? <VpValidationBadge compact /> : null}
      </span>
    )
  }
  return <span className="dim">—</span>
}

function fmtRvol(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return v.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function jevCell(health: string): ReactNode {
  if (health === '—') return <span className="dim">—</span>
  const tone = jevHealthTone(health)
  const dot = tone === 'green' ? '' : tone === 'amber' ? ' is-amber' : tone === 'red' ? ' is-sell' : ' is-off'
  const text = health === 'ok' || health === 'healthy' ? 'OK' : health.charAt(0).toUpperCase() + health.slice(1)
  return (
    <span className="opps-jev">
      <i className={`iv-dot${dot}`} />
      {text}
    </span>
  )
}

function entryGateCell(gate: string): ReactNode {
  if (gate === 'PASS') return <span className="ok">OK</span>
  if (gate === 'BLOQUÉ') return <span className="neg">Bloqué</span>
  return <span className="dim">{gate}</span>
}

function confidencePct(row: ScreenerDecisionRow): string {
  if (row.confidence == null || !Number.isFinite(row.confidence)) return '—'
  return `${Math.round(row.confidence * 100)}`
}

function normalizeSymbolParam(raw: string | null): string | null {
  if (!raw) return null
  const s = raw.trim().toUpperCase()
  if (!s) return null
  if (s.length >= 6) return s
  return toEngineSymbol(s)
}

function pairTitle(symbol: string): string {
  if (symbol.endsWith('USDT')) return `${displaySymbol(symbol)} / USDT`
  return displaySymbol(symbol)
}

export function DecisionsPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [rows, setRows] = useState<ScreenerDecisionRow[]>([])
  const [eveBySymbol, setEveBySymbol] = useState<Map<string, EveDossierLite>>(
    () => new Map(),
  )
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [oppFilter, setOppFilter] = useState<OppFilter>('Tous')
  const [detail, setDetail] = useState<DecisionDetail | null>(null)
  const [whyDetail, setWhyDetail] = useState<DecisionDetail | null>(null)
  const [detailSym, setDetailSym] = useState<string | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [openPaperSymbols, setOpenPaperSymbols] = useState<ReadonlySet<string>>(() => new Set())
  /** Symbole → portefeuilles où il est ouvert (tous les livres, pas seulement IchiVol). */
  const [openBooksBySymbol, setOpenBooksBySymbol] = useState<ReadonlyMap<string, { code: string; label: string }[]>>(
    () => new Map(),
  )
  const [paperConfirm, setPaperConfirm] = useState<PaperConfirmState | null>(null)
  const [paperToast, setPaperToast] = useState<string | null>(null)
  const [paperConfirming, setPaperConfirming] = useState(false)
  const [paperConfirmError, setPaperConfirmError] = useState<string | null>(null)
  const [paperMsg, setPaperMsg] = useState<string | null>(null)
  const [paperBusy, setPaperBusy] = useState(false)
  const [saveBusy, setSaveBusy] = useState(false)
  const [saveMsg, setSaveMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const dialogRef = useRef<HTMLDialogElement>(null)
  const paperConfirmLock = useRef(false)
  const deepLinkHandled = useRef<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [res, eveRes] = await Promise.all([
        getScreener('1h'),
        fetch('/api/engine/eve/dossiers?limit=100', { credentials: 'include' })
          .then(async (r) => {
            if (!r.ok) return { results: [] as EveDossierLite[] }
            return (await r.json()) as { results?: EveDossierLite[] }
          })
          .catch(() => ({ results: [] as EveDossierLite[] })),
      ])
      setRows(res.rows ?? [])
      setEveBySymbol(latestDossierBySymbol(eveRes.results ?? []))
    } catch {
      setRows([])
      setEveBySymbol(new Map())
    } finally {
      setLoading(false)
    }
  }, [])

  const refreshOpenPaperSymbols = useCallback(async () => {
    try {
      const books = await loadAllBooks()
      if (books.length === 0) throw new Error('no books')
      const bySymbol = new Map<string, { code: string; label: string }[]>()
      for (const b of books) {
        for (const p of b.overview.positions ?? []) {
          if (String(p.status).toUpperCase() !== 'OPEN') continue
          const list = bySymbol.get(p.symbol) ?? []
          if (!list.some((x) => x.code === b.code)) list.push({ code: b.code, label: b.label })
          bySymbol.set(p.symbol, list)
        }
      }
      setOpenBooksBySymbol(bySymbol)
      // « Déjà ouvert » pour le ticket manuel = déjà en lot sur IchiVol (un lot par marché et par livre).
      setOpenPaperSymbols(
        new Set([...bySymbol].filter(([, l]) => l.some((x) => x.code === BASELINE_PORTFOLIO_CODE)).map(([sym]) => sym)),
      )
    } catch {
      try {
        const [user, auto] = await Promise.all([
          listPaperPositions({ source: 'user_confirmed', status: 'OPEN' }),
          listPaperPositions({ source: 'auto_watchlist', status: 'OPEN' }),
        ])
        setOpenPaperSymbols(new Set([...user, ...auto].map((p) => p.symbol)))
      } catch {
        /* keep previous */
      }
    }
  }, [])

  useEffect(() => {
    void load()
    void refreshOpenPaperSymbols()
  }, [load, refreshOpenPaperSymbols])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return rows.filter((r) => {
      const cycle = cycleFromRow(r)
      if (oppFilter !== 'Tous' && cycle !== oppFilter) return false
      if (!q) return true
      const base = displaySymbol(r.symbol).toLowerCase()
      const full = r.symbol.toLowerCase()
      return base.includes(q) || full.includes(q)
    })
  }, [rows, query, oppFilter])

  const whyRow = useMemo(() => {
    const triggered = rows.filter((r) => cycleFromRow(r) === 'TRIGGERED')
    const pool = triggered.length ? triggered : rows
    if (!pool.length) return null
    return [...pool].sort((a, b) => (b.confidence ?? 0) - (a.confidence ?? 0))[0] ?? null
  }, [rows])

  useEffect(() => {
    const symbol = whyRow?.symbol
    if (!symbol) {
      setWhyDetail(null)
      return
    }
    let cancelled = false
    getDecisionDetail(symbol, '1h', false)
      .then((d) => {
        if (!cancelled) setWhyDetail(d)
      })
      .catch(() => {
        if (!cancelled) setWhyDetail(null)
      })
    return () => {
      cancelled = true
    }
  }, [whyRow?.symbol])

  const closeDialog = useCallback(() => {
    dialogRef.current?.close()
    setDetailSym(null)
    setDetail(null)
    setDetailLoading(false)
    setPaperMsg(null)
    setSaveMsg(null)
    const next = new URLSearchParams(searchParams)
    if (next.has('symbol') || next.has('open')) {
      next.delete('symbol')
      next.delete('open')
      setSearchParams(next, { replace: true })
    }
  }, [searchParams, setSearchParams])

  const openDecision = useCallback(
    async (symbol: string, opts?: { keepQuery?: boolean }) => {
      const sym = symbol.toUpperCase()
      setDetailSym(sym)
      setDetail(null)
      setDetailLoading(true)
      setPaperMsg(null)
      dialogRef.current?.showModal()
      if (!opts?.keepQuery) {
        const next = new URLSearchParams(searchParams)
        next.set('symbol', sym)
        setSearchParams(next, { replace: true })
      }
      try {
        const d = await getDecisionDetail(sym, '1h', false)
        setDetail(d)
      } catch {
        setDetail(null)
      } finally {
        setDetailLoading(false)
      }
    },
    [searchParams, setSearchParams],
  )

  // Deep-link Marché → /app/opportunites?symbol=…&open=1
  useEffect(() => {
    const sym = normalizeSymbolParam(searchParams.get('symbol'))
    const open = searchParams.get('open') === '1'
    if (!sym || !open) return
    const key = `${sym}|open`
    if (deepLinkHandled.current === key) return
    deepLinkHandled.current = key
    void openDecision(sym, { keepQuery: true })
  }, [searchParams, openDecision])

  // ?symbol= alone (sans open) : ouvre aussi la fiche
  useEffect(() => {
    const sym = normalizeSymbolParam(searchParams.get('symbol'))
    const open = searchParams.get('open') === '1'
    if (!sym || open) return
    const key = `${sym}|view`
    if (deepLinkHandled.current === key || deepLinkHandled.current === `${sym}|open`) return
    deepLinkHandled.current = key
    void openDecision(sym, { keepQuery: true })
  }, [searchParams, openDecision])

  async function startPaperOpen() {
    if (!detailSym || paperBusy || paperConfirming) return
    setPaperBusy(true)
    setPaperConfirmError(null)
    setPaperMsg(null)
    setSaveMsg(null)
    try {
      const tf = detail?.timeframe || '1h'
      const intent = await proposePaperTrade(detailSym, tf).catch(() => null)
      setPaperConfirm({
        symbol: detailSym,
        timeframe: tf,
        intent: intent ?? detail?.order_intent ?? null,
        // Déjà en lot sur IchiVol (un lot par marché) : on propose directement Sessions.
        defaultPortfolio: openPaperSymbols.has(detailSym) ? SESSIONS_CODE : BASELINE_PORTFOLIO_CODE,
        detail,
      })
      // La fiche est un <dialog> modal (top layer) : tant qu'elle est ouverte, le ticket reste derrière.
      dialogRef.current?.close()
    } finally {
      setPaperBusy(false)
    }
  }

  /** Enregistrement journal indépendant de l’ouverture paper. */
  async function saveDecisionToJournal() {
    if (!detailSym || saveBusy || detailLoading) return
    setSaveBusy(true)
    setSaveMsg(null)
    setPaperMsg(null)
    try {
      const tf = detail?.timeframe || '1h'
      const gate = detail?.pipeline?.decision ?? 'WATCH'
      const pipe = detail ? pipelineFromDecisionDetail(detail) : null
      const dir = pipe?.direction
      const bias =
        dir === 'SHORT' ? 'BEARISH' : dir === 'LONG' ? 'BULLISH' : 'NEUTRAL'
      const row = await confirmUserDecision({
        symbol: detailSym,
        interval: tf,
        bias,
        rvol: detail?.rvol ?? 0,
        signalKind:
          detail?.decision ??
          (gate === 'SELL' ? 'SELL' : gate === 'BUY' ? 'BUY' : 'WATCH'),
        gateDecision: gate,
        confidence: detail?.confidence,
      })
      const deduped = row.deduped === true
      setSaveMsg({
        ok: true,
        text: deduped
          ? `${displaySymbol(detailSym)} · déjà enregistrée dans le Journal`
          : `${displaySymbol(detailSym)} · décision enregistrée dans le Journal`,
      })
    } catch (err: unknown) {
      setSaveMsg({
        ok: false,
        text: err instanceof Error ? err.message : 'Enregistrement impossible',
      })
    } finally {
      setSaveBusy(false)
    }
  }

  async function executePaperConfirm(order: ManualOrderInput) {
    if (!paperConfirm || paperConfirmLock.current) return
    paperConfirmLock.current = true
    setPaperConfirming(true)
    setPaperConfirmError(null)
    try {
      const sameDetail = paperConfirm.detail?.symbol === paperConfirm.symbol ? paperConfirm.detail : null
      const gate =
        paperConfirm.intent?.pipeline_decision ?? sameDetail?.pipeline?.decision ?? 'WATCH'
      const pos = await openPaperPosition(paperConfirm.symbol, paperConfirm.timeframe, order)
      let journalWarn = ''
      try {
        await confirmUserDecision({
          symbol: paperConfirm.symbol,
          interval: paperConfirm.timeframe,
          bias: gate === 'SELL' ? 'BEARISH' : gate === 'BUY' ? 'BULLISH' : 'NEUTRAL',
          rvol: sameDetail?.rvol ?? 0,
          signalKind:
            sameDetail?.decision ??
            (gate === 'SELL' ? 'SELL' : gate === 'BUY' ? 'BUY' : 'WATCH'),
          gateDecision: gate,
          confidence: sameDetail?.confidence,
        })
      } catch {
        journalWarn = ' · journal non enregistré (réessayer depuis le Journal)'
      }
      const already = pos.already_open === true || pos.created === false
      const pfLabel = order.portfolioCode === SESSIONS_CODE ? 'Sessions' : 'IchiVol'
      // La fiche est fermée pendant le ticket : le résultat s'affiche en tête de page.
      setPaperToast(
        (already
          ? `${displaySymbol(pos.symbol)} · déjà dans ${pfLabel} — achat verrouillé`
          : `${displaySymbol(pos.symbol)} · achat paper ouvert sur ${pfLabel} @ ${pos.entry_price}`) +
          journalWarn,
      )
      if ((order.portfolioCode ?? BASELINE_PORTFOLIO_CODE) === BASELINE_PORTFOLIO_CODE) {
        setOpenPaperSymbols((prev) => new Set([...prev, pos.symbol]))
      }
      setPaperConfirm(null)
      void refreshOpenPaperSymbols()
    } catch (err: unknown) {
      const raw = err instanceof Error ? err.message : 'Échec paper'
      setPaperConfirmError(raw.replace(/^[a-z_]+: /, ''))
    } finally {
      setPaperConfirming(false)
      paperConfirmLock.current = false
    }
  }

  const whyBase = whyRow ? displaySymbol(whyRow.symbol) : '—'
  const whyCycle = whyRow ? cycleFromRow(whyRow) : '—'

  const detailPipeline = detail ? pipelineFromDecisionDetail(detail) : null
  const detailCycle = detail ? cycleFromRow(detail) : '—'
  const detailRvol =
    detail?.rvol != null && Number.isFinite(detail.rvol)
      ? `${detail.rvol.toLocaleString('fr-FR', { maximumFractionDigits: 2, minimumFractionDigits: 1 })}×`
      : '—'
  const detailConf =
    detail?.confidence != null && Number.isFinite(detail.confidence)
      ? `${Math.round(detail.confidence * 100)} / 100`
      : '—'
  const alreadyOpen = detailSym ? openPaperSymbols.has(detailSym) : false
  const openIn = detailSym ? (openBooksBySymbol.get(detailSym) ?? []) : []
  const detailEveDossier = detailSym
    ? eveBySymbol.get(String(detailSym).toUpperCase())
    : undefined
  const detailEve = detailEveDossier ? overlayFromDossier(detailEveDossier) : null

  const whyEveDossier = whyRow ? eveBySymbol.get(String(whyRow.symbol).toUpperCase()) : undefined
  const whyEve = whyEveDossier ? overlayFromDossier(whyEveDossier) : null
  const whyConf =
    whyRow?.confidence != null && Number.isFinite(whyRow.confidence)
      ? whyRow.confidence.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
      : '—'
  const whyDir = whyRow ? directionCell(whyRow) : null
  const whyInvalidation = whyDetail?.invalidation?.[0] ? labelEngineCode(whyDetail.invalidation[0]) : '—'

  return (
    <div className="opps-page">
      <div className="iv-ph">
        <div>
          <div className="iv-meta">Opportunités · de l’observation à la décision</div>
          <h1>Opportunités</h1>
          <p>Les 5 portes du moteur, puis Ève accepte ou refuse quand son pilote est actif. Paper seulement.</p>
        </div>
        <div className="iv-ph-act">
          <div className="iv-seg" role="group" aria-label="Filtrer par cycle">
            {(['Tous', 'ARMED', 'TRIGGERED', 'WATCH'] as OppFilter[]).map((t) => (
              <button
                key={t}
                type="button"
                className={oppFilter === t ? 'is-on' : ''}
                aria-pressed={oppFilter === t}
                onClick={() => setOppFilter(t)}
              >
                {FILTER_FR[t]}
              </button>
            ))}
          </div>
          <input
            type="search"
            id="opp-search"
            className="iv-input opps-search"
            placeholder="Rechercher un actif…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
      </div>

      {paperToast && (
        <div className="opps-toast" role="status">
          <span>{paperToast}</span>
          <button type="button" className="iv-btn iv-btn--ghost iv-btn--sm" onClick={() => setPaperToast(null)} aria-label="Masquer">
            ×
          </button>
        </div>
      )}

      <div className="iv-grid">
        <section className="iv-card iv-s8 iv-m-s12 opps-matrix">
          <div className="iv-card-head">
            <div className="iv-card-tabs">
              <span className="iv-card-tab is-on">Matrice de décision</span>
            </div>
            <div className="iv-card-tools">
              <span>{loading ? '—' : `${filtered.length} actifs`}</span>
              <span>Clôture 1H</span>
              <span className={eveBySymbol.size ? 'cy' : ''}>Ève {eveBySymbol.size || '—'}</span>
            </div>
          </div>
          <div className="iv-card-body is-flush iv-table-wrap">
            <table className="iv-table opps-table">
              <thead>
                <tr>
                  <th>Actif</th>
                  <th>Dir.</th>
                  {GATES.map((g) => (
                    <th key={g.id} className="c" title={g.label}>
                      {g.short}
                    </th>
                  ))}
                  <th className="n">RVOL</th>
                  <th className="n">Conf.</th>
                  <th>Cycle</th>
                  <th title="Ce qu’Ève répond : acheter, vendre à découvert, garder, s’abstenir">Décision Ève</th>
                  <th title="JEV a-t-il répondu correctement ?">JEV</th>
                  <th title="Filtre avant ouverture paper (confiance / setup)">Filtre entrée</th>
                  <th title="Le Risk Kernel autorise-t-il l’ouverture paper ?">Risque</th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={14} className="opps-empty">
                      {loading ? 'Chargement…' : 'Aucune ligne'}
                    </td>
                  </tr>
                ) : (
                  filtered.map((r) => {
                    const cycle = cycleFromRow(r)
                    const dossier = eveBySymbol.get(String(r.symbol).toUpperCase())
                    const eve = dossier ? overlayFromDossier(dossier) : null
                    const conf = eve && eve.confidenceLabel !== '—' ? eve.confidenceLabel : confidencePct(r)
                    return (
                      <tr
                        key={r.symbol}
                        className={`opps-row${whyRow?.symbol === r.symbol ? ' is-selected' : ''}`}
                        tabIndex={0}
                        onClick={() => void openDecision(r.symbol)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            void openDecision(r.symbol)
                          }
                        }}
                      >
                        <td className="sym">
                          {displaySymbol(r.symbol)}
                          <small>{r.symbol}</small>
                        </td>
                        <td>{directionCell(r)}</td>
                        {GATES.map((g) => (
                          <td key={g.id} className="c">
                            <GatePip row={r} gate={g} />
                          </td>
                        ))}
                        <td className={`n${r.rvol != null && r.rvol >= 1.5 ? ' ok' : ''}`}>{fmtRvol(r.rvol)}</td>
                        <td className="n">{conf === '—' ? '—' : conf.endsWith('%') ? conf : `${conf} %`}</td>
                        <td>{cycleTag(cycle)}</td>
                        <td>{eve ? eveTag(eve.action) : <span className="dim">—</span>}</td>
                        <td>{eve ? jevCell(eve.jevHealth) : <span className="dim">—</span>}</td>
                        <td>{eve ? entryGateCell(eve.entryGate) : <span className="dim">—</span>}</td>
                        <td className="opps-risk">
                          {eve && eve.risk !== '—' ? <span title={eve.risk}>{eve.risk}</span> : <span className="dim">—</span>}
                        </td>
                      </tr>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>
          <div className="iv-card-foot opps-legend">
            {GATES.map((g) => (
              <span key={g.id}>
                {g.short} · {g.label}
              </span>
            ))}
            <span className="opps-vp">
              <i className="vp-validation-badge opps-vp-key" aria-hidden />
              {VP_VALIDATION_BADGE_LABEL}
            </span>
          </div>
        </section>

        <div className="iv-s4 iv-m-s12 opps-side">
          <section className="iv-card iv-glow">
            <div className="iv-card-head">
              <div className="iv-card-tabs">
                <span className="iv-card-tab is-on">{whyRow ? `Pourquoi ${whyBase} ?` : 'Pourquoi — ?'}</span>
              </div>
              <div className="iv-card-tools">Conf. {whyConf}</div>
            </div>
            <div className="iv-card-body">
              <div className="opps-why-head">
                {cycleTag(whyCycle)}
                {whyDir}
              </div>
              <p className="iv-note opps-why-text">
                {whyDetail ? buildDecisionSummary(whyDetail) : whyRow ? 'Lecture moteur en cours…' : '—'}
              </p>
              <div className="iv-cap opps-cap">Lecture portes</div>
              <div className="opps-gates">
                {GATES.map((g) => {
                  const st = whyRow?.pipeline?.stages?.find((s) => s.id === g.id)
                  return (
                    <div className="opps-gate-row" key={g.id}>
                      {whyRow ? <GatePip row={whyRow} gate={g} /> : <span className="opps-gate is-none">·</span>}
                      <span className="opps-gate-name">{g.label}</span>
                      <span className="opps-gate-sum">{st?.summary || gateText(whyRow ? gateStatus(whyRow, g.id) : null)}</span>
                    </div>
                  )
                })}
              </div>
              <div className="opps-levels">
                <div className="iv-field">
                  <label>Déclenchement</label>
                  <div className="opps-level">—</div>
                </div>
                <div className="iv-field">
                  <label>Invalidation</label>
                  <div className={`opps-level${whyInvalidation !== '—' ? ' neg' : ''}`}>{whyInvalidation}</div>
                </div>
              </div>
              <button
                type="button"
                className="iv-btn iv-btn--primary opps-open"
                disabled={!whyRow}
                onClick={() => whyRow && void openDecision(whyRow.symbol)}
              >
                {whyRow ? 'Ouvrir la fiche de décision →' : '—'}
              </button>
            </div>
          </section>

          <section className="iv-card">
            <div className="iv-card-head">
              <div className="iv-card-tabs">
                <span className="iv-card-tab is-on">Décision Ève</span>
              </div>
              <div className="iv-card-tools opps-dossier">{whyEve ? `Dossier ${whyEve.dossierId}` : '—'}</div>
            </div>
            <div className="iv-card-body">
              {whyEve ? (
                <>
                  <div className="opps-verdict">
                    <span className="opps-verdict-box">
                      <span className="k">Moteur</span>
                      {whyCycle === '—' ? '—' : CYCLE_FR[whyCycle]}
                    </span>
                    <span className="opps-verdict-ar" aria-hidden>
                      →
                    </span>
                    <span className="opps-verdict-box is-eve">
                      <span className="k">Ève</span>
                      {eveTag(whyEve.action)}
                    </span>
                  </div>
                  <div className="opps-rows">
                    <div className="iv-row">
                      Lecture portes<span className="iv-row-v">{whyEve.baseline}</span>
                    </div>
                    <div className="iv-row">
                      JEV<span className="iv-row-v">{jevCell(whyEve.jevHealth)}</span>
                    </div>
                    <div className="iv-row">
                      Filtre avant ouverture<span className="iv-row-v">{entryGateCell(whyEve.entryGate)}</span>
                    </div>
                    <div className="iv-row">
                      Risk Kernel<span className="iv-row-v">{whyEve.risk}</span>
                    </div>
                  </div>
                </>
              ) : (
                <p className="iv-note opps-noeve">
                  {whyRow ? 'Pas encore de décision d’Ève sur ce symbole.' : '—'}{' '}
                  {whyRow ? (
                    <Link className="opps-link" to={`/app/agents?symbol=${encodeURIComponent(whyRow.symbol)}`}>
                      Demander son avis →
                    </Link>
                  ) : null}
                </p>
              )}
            </div>
          </section>

          <section className="iv-card">
            <div className="iv-card-head">
              <div className="iv-card-tabs">
                <span className="iv-card-tab is-on">De l’observation à la décision</span>
              </div>
            </div>
            <div className="iv-card-body">
              <div className="opps-cycle">
                {(['WATCH', 'ARMED', 'TRIGGERED', 'ACCEPTÉ', 'REFUSÉ'] as const).map((s, i) => (
                  <span key={s}>
                    {i ? <i aria-hidden>→</i> : null}
                    {cycleTag(s)}
                  </span>
                ))}
              </div>
              <p className="iv-note">
                Les 5 portes = lecture marché (Ichimoku × RVOL). Ensuite, si son pilote est actif, Ève accepte (achat
                ou vente à découvert) ou refuse (garder, s’abstenir). <span className="iv-kw">JEV</span> = JEV a
                répondu. <span className="iv-kw">Filtre entrée</span> = garde-fou avant d’ouvrir.{' '}
                <span className="iv-kw">Risque</span> = le Risk Kernel autorise ou bloque. Tirets = pas encore de
                décision d’Ève sur ce symbole.
              </p>
            </div>
          </section>
        </div>
      </div>

      <dialog
        id="detail"
        className="opps-dialog"
        ref={dialogRef}
        onClose={() => {
          setDetailSym(null)
          setDetail(null)
          setDetailLoading(false)
          setPaperMsg(null)
          setSaveMsg(null)
        }}
      >
        {detailSym ? (
          <div className="dialog-body opps-dialog-body">
            <div className="opps-dialog-head">
              <div>
                <div className="iv-meta">Fiche de décision · Ichimoku × RVOL · 1H</div>
                <h2>{pairTitle(detailSym)}</h2>
              </div>
              <button type="button" className="iv-btn iv-btn--ghost opps-close" onClick={closeDialog} aria-label="Fermer">
                ×
              </button>
            </div>
            <div className="opps-dialog-sub">
              {cycleTag(detailCycle)}
              <span className="iv-cap">
                {detail?.strategy_version ? detail.strategy_version : ''}
                {detailLoading ? ' chargement…' : ''}
              </span>
            </div>

            <div className="opps-dialog-grid">
              <div className="opps-dialog-block">
                <div className="iv-cap opps-cap">Décision Ève</div>
                {detailEve ? (
                  <>
                    <div className="iv-row">
                      Elle décide<span className="iv-row-v">{eveTag(detailEve.action)}</span>
                    </div>
                    <div className="iv-row">
                      Lecture portes<span className="iv-row-v">{detailEve.baseline}</span>
                    </div>
                    <div className="iv-row">
                      JEV
                      <span className="iv-row-v">
                        {badge(
                          detailEve.jevHealth === 'ok' || detailEve.jevHealth === 'healthy'
                            ? 'OK'
                            : detailEve.jevHealth === '—'
                              ? '—'
                              : 'PANNE / LENT',
                          jevHealthTone(detailEve.jevHealth) || 'gray',
                        )}
                      </span>
                    </div>
                    <div className="iv-row">
                      Filtre avant ouverture<span className="iv-row-v">{entryGateCell(detailEve.entryGate)}</span>
                    </div>
                    <div className="iv-row">
                      Risk Kernel<span className="iv-row-v">{detailEve.risk}</span>
                    </div>
                  </>
                ) : (
                  <p className="iv-note opps-noeve">
                    Pas encore de décision d’Ève sur ce symbole.{' '}
                    <Link className="opps-link" to={`/app/agents?symbol=${encodeURIComponent(detailSym ?? '')}`}>
                      Demander son avis →
                    </Link>
                  </p>
                )}
              </div>
              <div className="opps-dialog-block">
                <div className="iv-cap opps-cap">Lecture moteur</div>
                <div className="iv-row">
                  Direction
                  <span className="iv-row-v opps-dir-v">
                    {detailPipeline ? (
                      detailPipeline.direction === 'SHORT' ? (
                        <span className="iv-side is-short">VENTE</span>
                      ) : detailPipeline.direction === 'LONG' ? (
                        <span className="iv-side is-long">ACHAT</span>
                      ) : (
                        '—'
                      )
                    ) : (
                      '—'
                    )}
                    {isActionableBuySell(detailPipeline?.gateDecision) ? <VpValidationBadge /> : null}
                  </span>
                </div>
                <div className="iv-row">
                  Participation
                  <span className="iv-row-v">
                    {detail ? badge(gateText(gateStatus(detail, 'participation'))) : '—'}
                  </span>
                </div>
                <div className="iv-row">
                  RVOL<span className="iv-row-v">{detailRvol}</span>
                </div>
                <div className="iv-row">
                  Confiance<span className="iv-row-v">{detailConf}</span>
                </div>
                <div className="iv-row">
                  Déclenchement<span className="iv-row-v">—</span>
                </div>
                <div className="iv-row">
                  Invalidation
                  <span className="iv-row-v">
                    {detail?.invalidation?.[0] ? labelEngineCode(detail.invalidation[0]) : '—'}
                  </span>
                </div>
              </div>
            </div>

            {detail && detailPipeline && (
              <div className="engine-evidence">
                <p className="argumentaire">{buildDecisionSummary(detail)}</p>
                <DecisionPipelinePanel view={detailPipeline} />
                <SignalEvidenceCard detail={detail} />
              </div>
            )}
            {detailSym && <MtfPanel symbol={detailSym} timeframe={detail?.timeframe || '1h'} />}
            {detailSym && (
              <div className="ci-embed">
                <ChartIntelligencePanel
                  symbol={detailSym}
                  timeframe={detail?.timeframe || '1h'}
                  source="api"
                  variant="brief"
                  context="prep"
                />
              </div>
            )}
            <div className="opps-notice">
              {alreadyOpen
                ? `Position paper déjà ouverte sur ce symbole dans : ${openIn.map((b) => b.label).join(', ')}. Vous pouvez l’ouvrir sur Sessions.`
                : openIn.length > 0
                  ? `Position paper déjà ouverte sur ce symbole dans : ${openIn.map((b) => b.label).join(', ')}.`
                  : 'Lecture moteur + Chart Intelligence. Enregistrement journal ou ouverture paper au choix.'}
            </div>
            {saveMsg && (
              <div className={`opps-msg ${saveMsg.ok ? 'is-ok' : 'is-err'}`} role="status">
                {saveMsg.text}
              </div>
            )}
            {paperMsg && (
              <p className="iv-note opps-paper-msg" role="status">
                {paperMsg}
              </p>
            )}
            <div className="opps-dialog-actions">
              <button
                type="button"
                className="iv-btn"
                onClick={() => {
                  closeDialog()
                  navigate(`/app/market?symbol=${encodeURIComponent(detailSym)}`)
                }}
              >
                Voir le graphique
              </button>
              <button
                type="button"
                className="iv-btn"
                disabled={saveBusy || detailLoading || !detail}
                onClick={() => void saveDecisionToJournal()}
              >
                {saveBusy ? 'Enregistrement…' : 'Enregistrer la décision'}
              </button>
              <button
                type="button"
                className="iv-btn iv-btn--buy"
                disabled={paperBusy || paperConfirming || detailLoading}
                onClick={() => void startPaperOpen()}
              >
                {alreadyOpen
                  ? 'Déjà dans IchiVol · ouvrir sur Sessions →'
                  : paperBusy
                    ? 'Préparation paper…'
                    : 'Ouvrir une position paper →'}
              </button>
            </div>
          </div>
        ) : null}
      </dialog>

      {paperConfirm && (
        <PaperConfirmSheet
          symbol={paperConfirm.symbol}
          timeframe={paperConfirm.timeframe}
          symbolLabel={displaySymbol(paperConfirm.symbol)}
          intent={paperConfirm.intent}
          defaultPortfolio={paperConfirm.defaultPortfolio}
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
