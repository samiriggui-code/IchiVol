/**
 * Opportunités — port littéral de design-reference/ichivol-workspace `opportunites()` + page-head.
 * Classes HTML = maquette. Données = engine (pas de démo inventée ; manquant → « — »).
 * Paper : fiche dialog → aperçu (PaperConfirmSheet / previewPaperBuy) → openPaperPosition.
 */

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { DecisionPipelinePanel } from '../components/DecisionPipelinePanel'
import { PaperConfirmSheet } from '../components/PaperConfirmSheet'
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
import { displaySymbol } from '../lib/markets'
import {
  getPaperOverview,
  listPaperPositions,
  openPaperPosition,
  proposePaperTrade,
  type ManualOrderInput,
  type OrderIntent,
} from '../lib/paper'
import { confirmUserDecision } from '../lib/userDecisions'
import {
  maquetteGateBadge,
  type MaquetteBadgeTone,
} from './market/marketMaquetteHelpers'
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
}

function badge(text: string, tone: MaquetteBadgeTone | string = ''): ReactNode {
  let inferred = tone
  if (!inferred) {
    inferred = /PASSE|ACCEPTÉ|OUVERTE|VALIDÉ|DÉCLENCHÉ|DECLENCHE/i.test(text)
      ? 'green'
      : /REFUS|BLOQU|ERREUR|ÉCHEC/i.test(text)
        ? 'red'
        : /PRUDENCE|ARMÉ|ARME|VEILLE/i.test(text)
          ? 'amber'
          : ''
  }
  return <span className={`tag ${inferred}`.trim()}>{text}</span>
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

function stageBadge(row: ScreenerDecisionRow, stageId: string): ReactNode {
  const stages = row.pipeline?.stages
  const st = stages?.find((s) => s.id === stageId)
  if (!st) return badge('—', 'gray')
  const b = maquetteGateBadge(st.status)
  // Maquette matrice uses BLOQUÉ instead of ÉCHEC for fail on some gates
  if (b.text === 'ÉCHEC') return badge('BLOQUÉ', 'red')
  return badge(b.text, b.tone)
}

function participationBadge(row: ScreenerDecisionRow): ReactNode {
  if (row.pipeline?.stages?.some((s) => s.id === 'participation')) {
    return stageBadge(row, 'participation')
  }
  if (row.rvol == null || !Number.isFinite(row.rvol)) return badge('—', 'gray')
  return row.rvol >= 1.5 ? badge('PASSE') : badge('PRUDENCE', 'amber')
}

function directionCell(row: ScreenerDecisionRow): ReactNode {
  if (row.direction === 'SHORT' || row.decision === 'SELL' || row.decision === 'STRONG_SELL') {
    return <span className="down">↓ Vente</span>
  }
  if (row.direction === 'LONG' || row.decision === 'BUY' || row.decision === 'STRONG_BUY') {
    return <span className="up">↑ Achat</span>
  }
  return <span>—</span>
}

function confidencePct(row: ScreenerDecisionRow): string {
  if (row.confidence == null || !Number.isFinite(row.confidence)) return '—'
  return `${Math.round(row.confidence * 100)}`
}

function normalizeSymbolParam(raw: string | null): string | null {
  if (!raw) return null
  const s = raw.trim().toUpperCase()
  if (!s) return null
  if (s.endsWith('USDT') || s.length >= 6) return s
  return `${s}USDT`
}

function pairTitle(symbol: string): string {
  if (symbol.endsWith('USDT')) return `${displaySymbol(symbol)} / USDT`
  return displaySymbol(symbol)
}

export function DecisionsPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [rows, setRows] = useState<ScreenerDecisionRow[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [oppFilter, setOppFilter] = useState<OppFilter>('Tous')
  const [detail, setDetail] = useState<DecisionDetail | null>(null)
  const [whyDetail, setWhyDetail] = useState<DecisionDetail | null>(null)
  const [detailSym, setDetailSym] = useState<string | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [openPaperSymbols, setOpenPaperSymbols] = useState<ReadonlySet<string>>(() => new Set())
  const [paperConfirm, setPaperConfirm] = useState<PaperConfirmState | null>(null)
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
      const res = await getScreener('1h')
      setRows(res.rows ?? [])
    } catch {
      setRows([])
    } finally {
      setLoading(false)
    }
  }, [])

  const refreshOpenPaperSymbols = useCallback(async () => {
    try {
      const ov = await getPaperOverview()
      const fromOverview = ov.positions
        .filter((p) => String(p.status).toUpperCase() === 'OPEN')
        .map((p) => p.symbol)
      setOpenPaperSymbols(new Set(fromOverview))
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
    if (openPaperSymbols.has(detailSym)) {
      setPaperMsg(`${displaySymbol(detailSym)} · déjà ouvert — pas de 2ᵉ achat`)
      return
    }
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
      })
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
      const sameDetail = detail?.symbol === paperConfirm.symbol ? detail : null
      const gate =
        paperConfirm.intent?.pipeline_decision ?? sameDetail?.pipeline?.decision ?? 'WATCH'
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
        journalWarn = ' · journal non enregistré (réessayer depuis le Journal)'
      }
      const already = pos.already_open === true || pos.created === false
      setPaperMsg(
        (already
          ? `${displaySymbol(pos.symbol)} · déjà en portefeuille — achat verrouillé`
          : `${displaySymbol(pos.symbol)} · paper ${pos.direction} @ ${pos.entry_price}`) +
          journalWarn,
      )
      setOpenPaperSymbols((prev) => new Set([...prev, pos.symbol]))
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

  return (
    <div className="opps-page">
      <div className="page-head">
        <div>
          <div className="eyebrow">03 / ICHIVOL WORKSPACE</div>
          <h1>Opportunités</h1>
          <p className="subtitle">Chaque décision commence par une preuve.</p>
        </div>
        <div className="actions">{badge('CLOTURE 1H', 'gray')}</div>
      </div>

      <div className="toolbar">
        <input
          type="search"
          id="opp-search"
          placeholder="Rechercher un actif…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div className="segmented">
          {(['Tous', 'WATCH', 'ARMED', 'TRIGGERED'] as OppFilter[]).map((t) => (
            <button
              key={t}
              type="button"
              className={oppFilter === t ? 'active' : ''}
              onClick={() => setOppFilter(t)}
            >
              {FILTER_FR[t]}
            </button>
          ))}
        </div>
        <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--muted)' }}>
          {loading ? '—' : `${filtered.length} actifs`} · clôture 1H
        </span>
      </div>

      <section className="card">
        <div className="card-head">
          <h2>Matrice de décision</h2>
          {badge('5 PORTES', 'gray')}
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ACTIF</th>
                <th>DIRECTION</th>
                <th>PARTICIPATION</th>
                <th>STRUCTURE</th>
                <th>EMPLACEMENT</th>
                <th>RÉGIME</th>
                <th>CYCLE</th>
                <th>CONFIANCE</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={8}>
                    <b>—</b>
                    <small>{loading ? 'Chargement…' : 'Aucune ligne'}</small>
                  </td>
                </tr>
              ) : (
                filtered.map((r) => {
                  const base = displaySymbol(r.symbol)
                  const cycle = cycleFromRow(r)
                  return (
                    <tr
                      key={r.symbol}
                      className="clickable"
                      tabIndex={0}
                      onClick={() => void openDecision(r.symbol)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          void openDecision(r.symbol)
                        }
                      }}
                    >
                      <td>
                        <b>{base}</b>
                        <small>{r.symbol}</small>
                      </td>
                      <td>{directionCell(r)}</td>
                      <td>{participationBadge(r)}</td>
                      <td>{stageBadge(r, 'structure')}</td>
                      <td>{stageBadge(r, 'location')}</td>
                      <td>{stageBadge(r, 'regime')}</td>
                      <td>{badge(CYCLE_FR[cycle])}</td>
                      <td>
                        <span className="mono">{confidencePct(r)} %</span>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </section>

      <div style={{ height: 20 }} />

      <div className="grid">
        <section className="card">
          <div className="card-head">
            <h2>De l’observation à la décision</h2>
          </div>
          <div className="card-body">
            <div className="toolbar">
              {(['WATCH', 'ARMED', 'TRIGGERED', 'ACCEPTÉ', 'REFUSÉ'] as const).map((s, i) => (
                <span key={s}>
                  {i ? ' → ' : ''}
                  {badge(CYCLE_FR[s])}
                </span>
              ))}
            </div>
            <p style={{ fontSize: 12, color: 'var(--muted)' }}>
              Veille : pas d’entrée. Armé : le setup est prêt, le volume ou une porte retient.
              Déclenché : les cinq portes autorisent une lecture d’achat ou de vente. Accepté ou
              refusé : vous avez tranché. La confiance ne remplace pas le contrôle du risque.
            </p>
          </div>
        </section>

        <section className="card">
          <div className="card-head">
            <h2>{whyRow ? `Pourquoi ${whyBase} ?` : 'Pourquoi — ?'}</h2>
            {badge(whyCycle === '—' ? '—' : whyCycle)}
          </div>
          <div className="card-body">
            <p style={{ fontSize: 12 }}>
              {whyDetail
                ? buildDecisionSummary(whyDetail)
                : whyRow
                  ? 'Lecture moteur en cours…'
                  : '—'}
            </p>
            {whyRow ? (
              <button
                type="button"
                className="primary"
                onClick={() => void openDecision(whyRow.symbol)}
              >
                Ouvrir la fiche de décision →
              </button>
            ) : (
              <button type="button" className="primary" disabled>
                —
              </button>
            )}
          </div>
        </section>
      </div>

      <dialog
        id="detail"
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
          <div className="dialog-body">
            <div className="dialog-head">
              <h2>{pairTitle(detailSym)}</h2>
              <button type="button" onClick={closeDialog} aria-label="Fermer">
                ×
              </button>
            </div>
            {badge(detailCycle === '—' ? '—' : detailCycle)}
            <p>
              Fiche de décision · Ichimoku × RVOL · 1H
              {detail?.strategy_version ? ` · ${detail.strategy_version}` : ''}
              {detailLoading ? ' · chargement…' : ''}
            </p>
            <div className="statline">
              <span>Direction</span>
              <b>
                {detailPipeline
                  ? badge(
                      detailPipeline.direction === 'SHORT'
                        ? 'VENTE'
                        : detailPipeline.direction === 'LONG'
                          ? 'PASSE'
                          : '—',
                    )
                  : badge('—', 'gray')}
              </b>
            </div>
            <div className="statline">
              <span>Participation</span>
              <b>{detail ? participationBadge(detail) : badge('—', 'gray')}</b>
            </div>
            <div className="statline">
              <span>RVOL</span>
              <b>{detailRvol}</b>
            </div>
            <div className="statline">
              <span>Confiance</span>
              <b>{detailConf}</b>
            </div>
            <div className="statline">
              <span>Déclenchement</span>
              <b>—</b>
            </div>
            <div className="statline">
              <span>Invalidation</span>
              <b>{detail?.invalidation?.[0] ?? '—'}</b>
            </div>
            {detail && detailPipeline && (
              <div className="engine-evidence">
                <p className="argumentaire">{buildDecisionSummary(detail)}</p>
                <DecisionPipelinePanel view={detailPipeline} />
                <SignalEvidenceCard detail={detail} />
              </div>
            )}
            <div className="notice blue" style={{ marginTop: 20 }}>
              {alreadyOpen
                ? 'Position paper déjà ouverte sur ce symbole.'
                : 'Lecture moteur. Enregistrement journal ou ouverture paper au choix.'}
            </div>
            {saveMsg && (
              <div
                className="notice"
                style={{
                  marginTop: 12,
                  background: saveMsg.ok ? '#e7f3ee' : '#f8ecea',
                  borderColor: saveMsg.ok ? '#c5ddd4' : '#e8cfc9',
                  color: saveMsg.ok ? '#168579' : '#c8412f',
                }}
                role="status"
              >
                {saveMsg.text}
              </div>
            )}
            {paperMsg && (
              <p style={{ fontSize: 12, marginTop: 12 }} role="status">
                {paperMsg}
              </p>
            )}
            <button
              type="button"
              className="suggestion"
              style={{ width: '100%', marginTop: 16 }}
              disabled={alreadyOpen || paperBusy || paperConfirming || detailLoading}
              onClick={() => void startPaperOpen()}
            >
              {alreadyOpen
                ? 'Déjà ouvert en paper'
                : paperBusy
                  ? 'Préparation paper…'
                  : 'Ouvrir une position paper →'}
            </button>
            <div className="dialog-actions">
              <button
                type="button"
                onClick={() => {
                  closeDialog()
                  navigate(`/app/market?symbol=${encodeURIComponent(detailSym)}`)
                }}
              >
                Voir le graphique
              </button>
              <button
                type="button"
                className="primary"
                disabled={saveBusy || detailLoading || !detail}
                onClick={() => void saveDecisionToJournal()}
              >
                {saveBusy ? 'Enregistrement…' : 'Enregistrer la décision'}
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
