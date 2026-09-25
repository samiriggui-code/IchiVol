/**
 * FicheDecision — une fiche par type décision, réutilisée partout (shell deep-link).
 * Classes maquette : dialog-body / dialog-head / statline / tag / notice / table-wrap / segmented.
 * Donnée manquante → « — » + raison. Paper only.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { useNavigate } from 'react-router-dom'
import { PaperConfirmSheet } from '../PaperConfirmSheet'
import {
  afterPaperOrJournalAction,
  actionNoticeStyle,
} from '../../lib/actionFeedback'
import {
  buildDecisionSummary,
  labelDecision,
  labelDirection,
  labelPipelineGate,
  labelReason,
  termHint,
} from '../../lib/decisionLabels'
import {
  getDecisionDetail,
  type DecisionDetail,
  type PipelineGateLabel,
} from '../../lib/decisions'
import {
  pipelineFromDecisionDetail,
  stageStatusLabel,
  type PipelineStageStatus,
} from '../../lib/decisionPipeline'
import type { FicheDecisionTab } from '../../lib/ficheDeepLink'
import { displaySymbol } from '../../lib/markets'
import {
  getPaperOverview,
  listPaperPositions,
  openPaperPosition,
  previewPaperBuy,
  proposePaperTrade,
  type ManualOrderInput,
  type ManualPreview,
  type OrderIntent,
  type PaperPosition,
} from '../../lib/paper'
import {
  confirmUserDecision,
  listUserDecisions,
  type UserDecisionRow,
} from '../../lib/userDecisions'
import './ficheDialog.css'

type BadgeTone = 'green' | 'amber' | 'red' | 'gray' | ''

const TABS: { id: FicheDecisionTab; label: string }[] = [
  { id: 'synthese', label: 'Synthèse' },
  { id: 'portes', label: '5 portes' },
  { id: 'preuves', label: 'Preuves' },
  { id: 'plan', label: 'Plan' },
  { id: 'historique', label: 'Historique' },
]

const RVOL_THRESHOLD_FALLBACK = 1.5

function badge(text: string, tone: BadgeTone = ''): ReactNode {
  let inferred = tone
  if (!inferred) {
    inferred = /PASSE|ACCEPTÉ|OUVERTE|VALIDÉ|TRIGGERED/i.test(text)
      ? 'green'
      : /REFUS|BLOQU|ERREUR|ÉCHEC/i.test(text)
        ? 'red'
        : /PRUDENCE|ARMED|WATCH|ATTENTE/i.test(text)
          ? 'amber'
          : ''
  }
  return <span className={`tag ${inferred}`.trim()}>{text}</span>
}

function maquetteStatus(status: PipelineStageStatus): { text: string; tone: BadgeTone } {
  switch (status) {
    case 'pass':
      return { text: 'PASSE', tone: 'green' }
    case 'fail':
      return { text: 'ÉCHEC', tone: 'red' }
    case 'watch':
      return { text: 'PRUDENCE', tone: 'amber' }
    case 'pending':
      return { text: '—', tone: 'gray' }
    case 'skip':
      return { text: 'N/A', tone: 'gray' }
    default:
      return { text: stageStatusLabel(status), tone: 'gray' }
  }
}

function cycleFromDetail(d: DecisionDetail): string {
  const gate = d.pipeline?.decision?.toUpperCase?.() ?? ''
  if (gate === 'BUY' || gate === 'SELL') return 'TRIGGERED'
  if (gate === 'WATCH') return 'ARMED'
  if (gate === 'NO_TRADE') return 'WATCH'
  const dec = String(d.decision || '').toUpperCase()
  if (dec === 'STRONG_BUY' || dec === 'STRONG_SELL' || dec === 'BUY' || dec === 'SELL') {
    return 'TRIGGERED'
  }
  if (dec === 'WATCH') return 'ARMED'
  if (dec === 'WAIT') return 'WATCH'
  return '—'
}

function fmtTs(ts: number | null | undefined): string {
  if (ts == null || !Number.isFinite(ts)) return '— · horodatage moteur absent'
  const ms = ts < 1e12 ? ts * 1000 : ts
  const d = new Date(ms)
  if (Number.isNaN(+d)) return '— · horodatage invalide'
  return d.toLocaleString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function fmtNum(v: number | null | undefined, digits = 2): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return v.toLocaleString('fr-FR', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

function fmtPct01(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return `${Math.round(v * 100)} %`
}

function metaNum(meta: Record<string, unknown> | undefined, key: string): number | null {
  if (!meta) return null
  const v = meta[key]
  return typeof v === 'number' && Number.isFinite(v) ? v : null
}

function metaStr(meta: Record<string, unknown> | undefined, key: string): string | null {
  if (!meta) return null
  const v = meta[key]
  return typeof v === 'string' && v.trim() ? v : null
}

function ValueWithHint({
  value,
  term,
  missingReason,
}: {
  value: ReactNode
  term?: string
  missingReason?: string
}) {
  const hint = term ? termHint(term) : ''
  return (
    <b>
      {value}
      {missingReason ? (
        <span className="fiche-term-hint">{missingReason}</span>
      ) : hint ? (
        <span className="fiche-term-hint">{hint}</span>
      ) : null}
    </b>
  )
}

function CodeList({ codes, empty }: { codes: string[]; empty: string }) {
  if (!codes.length) return <p style={{ fontSize: 12, color: 'var(--muted)' }}>{empty}</p>
  return (
    <ul className="fiche-list">
      {codes.map((c) => (
        <li key={c}>{labelReason(c)}</li>
      ))}
    </ul>
  )
}

function rewardRisk(intent: OrderIntent | null): string {
  if (!intent) return '—'
  const entry = intent.entry_fill ?? intent.price
  const stop = intent.stop_price
  const tp = intent.take_profit_price
  if (entry == null || stop == null || tp == null) return '— · stop/cible incomplets'
  const risk = Math.abs(entry - stop)
  if (risk <= 0) return '— · distance stop nulle'
  const r = Math.abs(tp - entry) / risk
  return `${r.toLocaleString('fr-FR', { maximumFractionDigits: 2 })}R`
}

export function FicheDecision({
  symbol,
  timeframe,
  initialTab = 'synthese',
  onClose,
  asOfNote,
}: {
  symbol: string
  timeframe: string
  initialTab?: FicheDecisionTab
  onClose: () => void
  /** Journal : lecture live faute d’API as-of. */
  asOfNote?: string | null
}) {
  const navigate = useNavigate()
  const dialogRef = useRef<HTMLDialogElement>(null)
  const paperLock = useRef(false)

  const [tab, setTab] = useState<FicheDecisionTab>(initialTab)
  const [detail, setDetail] = useState<DecisionDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [intent, setIntent] = useState<OrderIntent | null>(null)
  const [intentLoading, setIntentLoading] = useState(false)
  const [preview, setPreview] = useState<ManualPreview | null>(null)
  const [openSymbols, setOpenSymbols] = useState<ReadonlySet<string>>(() => new Set())
  const [journalRows, setJournalRows] = useState<UserDecisionRow[]>([])
  const [pastPositions, setPastPositions] = useState<PaperPosition[]>([])
  const [histLoading, setHistLoading] = useState(false)
  const [saveBusy, setSaveBusy] = useState(false)
  const [paperBusy, setPaperBusy] = useState(false)
  const [paperConfirming, setPaperConfirming] = useState(false)
  const [paperConfirm, setPaperConfirm] = useState<{
    symbol: string
    timeframe: string
    intent: OrderIntent | null
  } | null>(null)
  const [paperConfirmError, setPaperConfirmError] = useState<string | null>(null)
  const [localNotice, setLocalNotice] = useState<{ ok: boolean; text: string } | null>(null)

  useEffect(() => {
    setTab(initialTab)
  }, [initialTab, symbol, timeframe])

  useEffect(() => {
    const el = dialogRef.current
    if (!el) return
    if (!el.open) el.showModal()
    const onClose = () => onClose()
    el.addEventListener('close', onClose)
    return () => el.removeEventListener('close', onClose)
  }, [onClose])

  const refreshOpen = useCallback(async () => {
    try {
      const ov = await getPaperOverview()
      setOpenSymbols(
        new Set(
          ov.positions
            .filter((p) => String(p.status).toUpperCase() === 'OPEN')
            .map((p) => p.symbol),
        ),
      )
    } catch {
      try {
        const [user, auto] = await Promise.all([
          listPaperPositions({ source: 'user_confirmed', status: 'OPEN' }),
          listPaperPositions({ source: 'auto_watchlist', status: 'OPEN' }),
        ])
        setOpenSymbols(new Set([...user, ...auto].map((p) => p.symbol)))
      } catch {
        /* keep */
      }
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setDetail(null)
    setIntent(null)
    setPreview(null)
    setLocalNotice(null)
    void refreshOpen()
    getDecisionDetail(symbol, timeframe, false)
      .then((d) => {
        if (!cancelled) setDetail(d)
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Chargement impossible')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [symbol, timeframe, refreshOpen])

  useEffect(() => {
    if (!detail || tab !== 'plan') return
    let cancelled = false
    setIntentLoading(true)
    proposePaperTrade(symbol, timeframe)
      .then((i) => {
        if (!cancelled) setIntent(i)
      })
      .catch(() => {
        if (!cancelled) setIntent(detail.order_intent ?? null)
      })
      .finally(() => {
        if (!cancelled) setIntentLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [detail, tab, symbol, timeframe])

  useEffect(() => {
    const active = intent ?? detail?.order_intent ?? null
    if (!active?.actionable || active.notional == null || active.stop_distance == null || !active.price) {
      setPreview(null)
      return
    }
    const stopPct = Math.min(0.3, Math.max(0.005, active.stop_distance / active.price))
    const tpR =
      active.targets?.[0]?.r_multiple != null && Number.isFinite(active.targets[0].r_multiple)
        ? Number(active.targets[0].r_multiple)
        : 2
    let cancelled = false
    previewPaperBuy(symbol, timeframe, {
      notional: active.notional,
      stopPct,
      takeProfitR: tpR,
    })
      .then((p) => {
        if (!cancelled) setPreview(p)
      })
      .catch(() => {
        if (!cancelled) setPreview(null)
      })
    return () => {
      cancelled = true
    }
  }, [intent, detail?.order_intent, symbol, timeframe])

  useEffect(() => {
    if (tab !== 'historique') return
    let cancelled = false
    setHistLoading(true)
    Promise.all([
      listUserDecisions(80).catch(() => [] as UserDecisionRow[]),
      listPaperPositions().catch(() => [] as PaperPosition[]),
    ])
      .then(([decisions, positions]) => {
        if (cancelled) return
        const sym = symbol.toUpperCase()
        setJournalRows(decisions.filter((d) => d.symbol.toUpperCase() === sym))
        setPastPositions(
          positions.filter(
            (p) =>
              p.symbol.toUpperCase() === sym &&
              String(p.status).toUpperCase() !== 'OPEN',
          ),
        )
      })
      .finally(() => {
        if (!cancelled) setHistLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [tab, symbol])

  const pipeline = useMemo(
    () => (detail ? pipelineFromDecisionDetail(detail) : null),
    [detail],
  )

  const ctx = useMemo(() => {
    const raw = (detail?.evidence?.context ?? detail?.context ?? {}) as Record<
      string,
      Record<string, unknown> | undefined
    >
    return {
      ichimoku: (raw.ichimoku ?? {}) as Record<string, unknown>,
      volume: (raw.volume ?? {}) as Record<string, unknown>,
      structure: (raw.structure ?? {}) as Record<string, unknown>,
      regime: (raw.regime ?? {}) as Record<string, unknown>,
    }
  }, [detail])

  const alreadyOpen = openSymbols.has(symbol)
  const gate = (detail?.pipeline?.decision ??
    intent?.pipeline_decision ??
    '') as string
  const gatesPassed = gate === 'BUY' || gate === 'SELL'
  const activeIntent = intent ?? detail?.order_intent ?? null

  const paperDisabledReason = alreadyOpen
    ? 'Déjà en portefeuille'
    : !gatesPassed && detail
      ? 'Portes non passées : avis Attente'
      : null

  async function saveDecision() {
    if (!detail || saveBusy) return
    setSaveBusy(true)
    setLocalNotice(null)
    try {
      const dir = pipeline?.direction
      const bias =
        dir === 'SHORT' ? 'BEARISH' : dir === 'LONG' ? 'BULLISH' : 'NEUTRAL'
      const row = await confirmUserDecision({
        symbol,
        interval: timeframe,
        bias,
        rvol: detail.rvol ?? 0,
        signalKind:
          detail.decision ??
          (gate === 'SELL' ? 'SELL' : gate === 'BUY' ? 'BUY' : 'WATCH'),
        gateDecision: gate || 'WATCH',
        confidence: detail.confidence,
      })
      const text = row.deduped
        ? `${displaySymbol(symbol)} · déjà enregistrée dans le Journal`
        : `${displaySymbol(symbol)} · décision enregistrée dans le Journal`
      setLocalNotice({ ok: true, text })
      afterPaperOrJournalAction(true, text)
    } catch (err: unknown) {
      const text = err instanceof Error ? err.message : 'Enregistrement impossible'
      setLocalNotice({ ok: false, text })
      afterPaperOrJournalAction(false, text)
    } finally {
      setSaveBusy(false)
    }
  }

  async function startPaper() {
    if (alreadyOpen || paperBusy || paperConfirming) return
    setPaperBusy(true)
    setPaperConfirmError(null)
    setLocalNotice(null)
    try {
      const i = await proposePaperTrade(symbol, timeframe).catch(
        () => detail?.order_intent ?? null,
      )
      setPaperConfirm({ symbol, timeframe, intent: i })
    } finally {
      setPaperBusy(false)
    }
  }

  async function executePaper(order: ManualOrderInput) {
    if (!paperConfirm || paperLock.current) return
    paperLock.current = true
    setPaperConfirming(true)
    setPaperConfirmError(null)
    try {
      const pos = await openPaperPosition(
        paperConfirm.symbol,
        paperConfirm.timeframe,
        order,
      )
      try {
        await confirmUserDecision({
          symbol: paperConfirm.symbol,
          interval: paperConfirm.timeframe,
          bias: 'BULLISH',
          rvol: detail?.rvol ?? 0,
          signalKind: detail?.decision ?? 'WATCH',
          gateDecision:
            paperConfirm.intent?.pipeline_decision ?? detail?.pipeline?.decision ?? 'WATCH',
          confidence: detail?.confidence,
        })
      } catch {
        /* journal best-effort */
      }
      const already = pos.already_open === true || pos.created === false
      const text = already
        ? `${displaySymbol(pos.symbol)} · déjà en portefeuille — achat verrouillé`
        : `${displaySymbol(pos.symbol)} · paper ${pos.direction} @ ${pos.entry_price}`
      setLocalNotice({ ok: !already || already, text })
      afterPaperOrJournalAction(true, text)
      setOpenSymbols((prev) => new Set([...prev, pos.symbol]))
      setPaperConfirm(null)
      void refreshOpen()
    } catch (err: unknown) {
      const raw = err instanceof Error ? err.message : 'Échec paper'
      setPaperConfirmError(raw.replace(/^[a-z_]+: /, ''))
      afterPaperOrJournalAction(false, raw)
    } finally {
      setPaperConfirming(false)
      paperLock.current = false
    }
  }

  const base = displaySymbol(symbol)
  const cycle = detail ? cycleFromDetail(detail) : '—'
  const summary = detail ? buildDecisionSummary(detail) : null
  const invalidation =
    detail?.invalidation?.[0] ??
    detail?.evidence?.invalidation?.[0] ??
    detail?.order_intent?.invalidation?.[0] ??
    null

  const whyNot =
    detail?.why_not ??
    (detail?.pipeline?.direction === 'SHORT'
      ? detail.evidence?.why_not_short
      : detail.evidence?.why_not_long) ??
    detail?.risks ??
    []
  const positive =
    detail?.positive_evidence ??
    detail?.evidence?.positive_evidence ??
    detail?.reasons ??
    []
  const contradictions =
    detail?.contradictions ?? detail?.evidence?.contradictions ?? []

  const ichiMeta = detail?.ichimoku?.metadata
  const tenkan = metaNum(ichiMeta, 'tenkan')
  const kijun = metaNum(ichiMeta, 'kijun')
  const tkCross =
    metaStr(ichiMeta, 'tk_cross') ??
    (typeof ctx.ichimoku.tk_state === 'string' ? ctx.ichimoku.tk_state : null)
  const priceVsCloud =
    metaStr(ichiMeta, 'price_vs_kumo') ??
    (typeof ctx.ichimoku.price_vs_cloud === 'string'
      ? String(ctx.ichimoku.price_vs_cloud)
      : null)
  const chikou =
    metaStr(ichiMeta, 'chikou_state') ??
    (typeof ctx.ichimoku.chikou_state === 'string'
      ? String(ctx.ichimoku.chikou_state)
      : null)

  const volumeType =
    detail?.volume_type ??
    detail?.rvol_detail?.volume_type ??
    (typeof ctx.volume.volume_type === 'string' ? ctx.volume.volume_type : null)

  const structureTrend =
    typeof ctx.structure.trend === 'string' ? ctx.structure.trend : null
  const bosState =
    typeof ctx.structure.breakout_state === 'string'
      ? ctx.structure.breakout_state
      : null
  const chochExplicit =
    typeof ctx.structure.choch === 'string'
      ? ctx.structure.choch
      : typeof ctx.structure.choch_state === 'string'
        ? ctx.structure.choch_state
        : null

  const hist = detail?.evidence?.historical
  const stale =
    detail?.data_quality?.stale === true || detail?.data_quality?.data_late === true

  function renderPortes() {
    if (!pipeline) {
      return (
        <p style={{ fontSize: 12, color: 'var(--muted)' }}>
          {loading ? 'Chargement…' : '— · pipeline indisponible'}
        </p>
      )
    }
    return (
      <>
        {pipeline.stages.map((stage) => {
          const st = maquetteStatus(stage.status)
          return (
            <div key={stage.id}>
              <div className="statline">
                <span>
                  {stage.label}
                  <span className="fiche-term-hint">{stage.question}</span>
                </span>
                <b>{badge(st.text === '—' ? '—' : st.text, st.tone)}</b>
              </div>
              <p style={{ fontSize: 12, color: 'var(--muted)', margin: '0 0 8px' }}>
                {stage.summary || '— · résumé moteur absent'}
                {stage.status === 'pending' ? ' (porte non encore calculée)' : ''}
              </p>
              {stage.codes.length > 0 && (
                <CodeList codes={stage.codes} empty="" />
              )}
            </div>
          )
        })}

        <div className="statline">
          <span>Prix vs nuage</span>
          <ValueWithHint
            term="Kumo"
            value={priceVsCloud ?? '—'}
            missingReason={
              priceVsCloud ? undefined : '— · price_vs_cloud / metadata absent'
            }
          />
        </div>
        <div className="statline">
          <span>Tenkan</span>
          <ValueWithHint
            term="Tenkan"
            value={tenkan != null ? fmtNum(tenkan, 4) : '—'}
            missingReason={tenkan != null ? undefined : '— · metadata.tenkan absent'}
          />
        </div>
        <div className="statline">
          <span>Kijun</span>
          <ValueWithHint
            term="Kijun"
            value={kijun != null ? fmtNum(kijun, 4) : '—'}
            missingReason={kijun != null ? undefined : '— · metadata.kijun absent'}
          />
        </div>
        <div className="statline">
          <span>TK cross</span>
          <b>{tkCross ?? '— · tk_cross absent'}</b>
        </div>
        <div className="statline">
          <span>Chikou</span>
          <ValueWithHint
            term="Chikou"
            value={chikou ?? '—'}
            missingReason={chikou ? undefined : '— · chikou_state absent'}
          />
        </div>
        <div className="statline">
          <span>RVOL</span>
          <ValueWithHint
            term="RVOL"
            value={
              detail?.rvol != null
                ? `${fmtNum(detail.rvol, 2)}× (seuil ≥ ${fmtNum(RVOL_THRESHOLD_FALLBACK, 1)})`
                : '—'
            }
            missingReason={
              detail?.rvol != null
                ? undefined
                : '— · RVOL indisponible · seuil UI de repli 1,5'
            }
          />
        </div>
        <div className="statline">
          <span>Type de volume</span>
          <b>{volumeType ?? '— · volume_type absent'}</b>
        </div>
        <div className="statline">
          <span>Structure / BOS</span>
          <ValueWithHint
            term="BOS"
            value={
              structureTrend || bosState
                ? `${structureTrend ?? '—'}${
                    bosState && bosState !== 'NONE' ? ` · BOS ${bosState}` : ''
                  }`
                : '—'
            }
            missingReason={
              structureTrend || bosState
                ? undefined
                : '— · context.structure absent'
            }
          />
        </div>
        <div className="statline">
          <span>CHoCH</span>
          <ValueWithHint
            term="CHoCH"
            value={chochExplicit ?? '—'}
            missingReason={
              chochExplicit ? undefined : '— · champ CHoCH non exposé par le moteur'
            }
          />
        </div>
        <div className="statline">
          <span>Emplacement</span>
          <ValueWithHint
            term="Location"
            value={
              pipeline.stages.find((s) => s.id === 'location')?.summary ?? '—'
            }
          />
        </div>
        <div className="statline">
          <span>Régime</span>
          <ValueWithHint
            term="Régime"
            value={
              (typeof ctx.regime.pipeline_regime === 'string'
                ? ctx.regime.pipeline_regime
                : null) ??
              pipeline.stages.find((s) => s.id === 'regime')?.summary ??
              '—'
            }
          />
        </div>
      </>
    )
  }

  function renderPreuves() {
    if (!detail) {
      return (
        <p style={{ fontSize: 12, color: 'var(--muted)' }}>
          {loading ? 'Chargement…' : '— · détail indisponible'}
        </p>
      )
    }
    const ev = detail.evidence
    return (
      <>
        <div className="statline">
          <span>Accord agents</span>
          <b>{fmtPct01(detail.agreement)}</b>
        </div>
        <p style={{ fontSize: 12, marginTop: 12 }}>
          <strong>Raisons</strong>
        </p>
        <CodeList codes={detail.reasons} empty="— · aucune raison moteur" />
        <p style={{ fontSize: 12, marginTop: 12 }}>
          <strong>Preuves positives</strong>
        </p>
        <CodeList codes={positive} empty="— · pas de preuve positive" />
        <p style={{ fontSize: 12, marginTop: 12 }}>
          <strong>Contradictions</strong>
        </p>
        <CodeList codes={contradictions} empty="— · aucune contradiction signalée" />
        <p style={{ fontSize: 12, marginTop: 12 }}>
          <strong>Pourquoi pas</strong>
        </p>
        <CodeList codes={whyNot} empty="— · why_not absent" />
        <p style={{ fontSize: 12, marginTop: 12 }}>
          <strong>Risques</strong>
        </p>
        <CodeList codes={detail.risks} empty="— · aucun risque listé" />

        <div className="statline" style={{ marginTop: 16 }}>
          <span>Échantillon</span>
          <ValueWithHint
            term="walk-forward"
            value={
              hist
                ? `${hist.sample_size} · ${hist.sample_quality} · ${hist.status}`
                : '—'
            }
            missingReason={hist ? undefined : '— · pas encore calculée pour ce signal'}
          />
        </div>
        {hist && (
          <>
            <div className="statline">
              <span>Calibration</span>
              <b>{ev?.calibration_note ?? '— · note absente'}</b>
            </div>
            <div className="statline">
              <span>Horizon</span>
              <b>{hist.horizon} barres</b>
            </div>
            <div className="statline">
              <span>Taux favorable</span>
              <b>
                {hist.favorable_rate != null
                  ? `${(hist.favorable_rate * 100).toFixed(1)} %`
                  : '—'}
              </b>
            </div>
            <div className="statline">
              <span>Moyenne / médiane</span>
              <b>
                {hist.mean_return_pct != null
                  ? `${(hist.mean_return_pct * 100).toFixed(2)} %`
                  : '—'}
                {' / '}
                {hist.median_return_pct != null
                  ? `${(hist.median_return_pct * 100).toFixed(2)} %`
                  : '—'}
              </b>
            </div>
            <div className="statline">
              <span>MFE / MAE</span>
              <b>
                {hist.mean_mfe_pct != null
                  ? `${(hist.mean_mfe_pct * 100).toFixed(2)} %`
                  : '—'}
                {' / '}
                {hist.mean_mae_pct != null
                  ? `${(hist.mean_mae_pct * 100).toFixed(2)} %`
                  : '—'}
              </b>
            </div>
          </>
        )}

        {ev?.ablation && ev.ablation.length > 0 && (
          <div className="table-wrap" style={{ marginTop: 16 }}>
            <table>
              <thead>
                <tr>
                  <th>ABLATION</th>
                  <th>N</th>
                  <th>FAVORABLE</th>
                  <th>MOYENNE</th>
                </tr>
              </thead>
              <tbody>
                {ev.ablation.map((row) => (
                  <tr key={row.label}>
                    <td>{row.label}</td>
                    <td className="mono">{row.sample_size}</td>
                    <td className="mono">
                      {row.favorable_rate != null
                        ? `${(row.favorable_rate * 100).toFixed(1)} %`
                        : '—'}
                    </td>
                    <td className="mono">
                      {row.mean_return_pct != null
                        ? `${(row.mean_return_pct * 100).toFixed(2)} %`
                        : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="statline">
          <span>Poids utilisés</span>
          <b>
            {detail.weights_used && Object.keys(detail.weights_used).length
              ? Object.entries(detail.weights_used)
                  .slice(0, 6)
                  .map(([k, v]) => `${k}=${String(v)}`)
                  .join(' · ')
              : '— · moteur sans poids'}
          </b>
        </div>
        <p style={{ fontSize: 10, color: 'var(--muted)', marginTop: 12 }}>
          {detail.strategy_version}
          {ev?.feature_version ? ` · features ${ev.feature_version}` : ''}
          {ev?.evidence_engine_version ? ` · evidence ${ev.evidence_engine_version}` : ''}
        </p>
      </>
    )
  }

  function renderPlan() {
    const i = activeIntent
    return (
      <>
        {intentLoading && (
          <p style={{ fontSize: 12, color: 'var(--muted)' }}>Calcul du plan…</p>
        )}
        {!i && !intentLoading && (
          <p style={{ fontSize: 12, color: 'var(--muted)' }}>
            — · order_intent indisponible
          </p>
        )}
        {i && (
          <>
            <div className="statline">
              <span>Statut</span>
              <b>
                {i.actionable
                  ? badge('PRÊT', 'green')
                  : badge(i.reason || 'BLOQUÉ', 'amber')}
              </b>
            </div>
            <div className="statline">
              <span>Entrée</span>
              <b className="mono">
                {fmtNum(i.entry_fill ?? i.price, 4)}
              </b>
            </div>
            <div className="statline">
              <span>Stop</span>
              <b className="mono">{fmtNum(i.stop_price, 4)}</b>
            </div>
            <div className="statline">
              <span>Cible</span>
              <b className="mono">{fmtNum(i.take_profit_price, 4)}</b>
            </div>
            <div className="statline">
              <span>Quantité</span>
              <b className="mono">
                {i.qty != null ? i.qty.toPrecision(4) : '— · qty absente'}
              </b>
            </div>
            <div className="statline">
              <span>Montant</span>
              <b className="mono">
                {i.notional != null ? `${fmtNum(i.notional, 2)} €` : '—'}
              </b>
            </div>
            <div className="statline">
              <span>Risque</span>
              <b>
                {i.risk_amount != null ? `${fmtNum(i.risk_amount, 2)} €` : '—'}
                {i.risk_pct != null ? ` · ${fmtPct01(i.risk_pct)}` : ''}
              </b>
            </div>
            <div className="statline">
              <span>R</span>
              <ValueWithHint term="R" value={rewardRisk(i)} />
            </div>
            <div className="statline">
              <span>Frais estimés (aller-retour cible)</span>
              <b>
                {preview?.costs?.round_trip_at_target != null
                  ? `${fmtNum(preview.costs.round_trip_at_target, 2)} €`
                  : '— · aperçu frais non calculé'}
              </b>
            </div>
          </>
        )}

        {preview?.scenarios ? (
          <div className="table-wrap" style={{ marginTop: 16 }}>
            <table>
              <thead>
                <tr>
                  <th>SCÉNARIO</th>
                  <th>NET €</th>
                  <th>% INVESTI</th>
                </tr>
              </thead>
              <tbody>
                {(
                  [
                    ['target', preview.scenarios.target],
                    ['stop', preview.scenarios.stop],
                    ['crash', preview.scenarios.crash],
                  ] as const
                ).map(([key, row]) => (
                  <tr key={key}>
                    <td>{row.label}</td>
                    <td className="mono">{fmtNum(row.net_eur, 2)}</td>
                    <td className="mono">
                      {row.pct_of_invested != null
                        ? `${(row.pct_of_invested * 100).toFixed(1)} %`
                        : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p style={{ fontSize: 10, color: 'var(--muted)' }}>
              Scénarios historiques — pas une prévision.
            </p>
          </div>
        ) : (
          <p style={{ fontSize: 12, color: 'var(--muted)', marginTop: 12 }}>
            — · scénarios absents (preview non disponible)
          </p>
        )}
      </>
    )
  }

  function renderHistorique() {
    if (histLoading) {
      return <p style={{ fontSize: 12, color: 'var(--muted)' }}>Chargement…</p>
    }
    return (
      <>
        <p style={{ fontSize: 12 }}>
          <strong>Décisions journal</strong>
        </p>
        {journalRows.length === 0 ? (
          <p style={{ fontSize: 12, color: 'var(--muted)' }}>
            — · aucune décision sauvegardée pour ce symbole
          </p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>DATE</th>
                  <th>PORTES</th>
                  <th>STATUT</th>
                </tr>
              </thead>
              <tbody>
                {journalRows.map((r) => (
                  <tr key={r.id}>
                    <td>{new Date(r.createdAt).toLocaleString('fr-FR')}</td>
                    <td>{r.gateDecision ?? '—'}</td>
                    <td>{r.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p style={{ fontSize: 12, marginTop: 16 }}>
          <strong>Positions passées</strong>
        </p>
        {pastPositions.length === 0 ? (
          <p style={{ fontSize: 12, color: 'var(--muted)' }}>
            — · aucune position paper clôturée
          </p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>SORTIE</th>
                  <th>SENS</th>
                  <th>PNL %</th>
                  <th>RAISON</th>
                </tr>
              </thead>
              <tbody>
                {pastPositions.slice(0, 20).map((p) => (
                  <tr key={p.id}>
                    <td>
                      {p.exit_time
                        ? new Date(p.exit_time).toLocaleString('fr-FR')
                        : '—'}
                    </td>
                    <td>{p.direction}</td>
                    <td className="mono">
                      {p.pnl_pct != null ? fmtNum(p.pnl_pct, 2) : '—'}
                    </td>
                    <td>{p.exit_reason ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </>
    )
  }

  return (
    <>
      <dialog
        ref={dialogRef}
        className="fiche-dialog"
        onCancel={(e) => {
          e.preventDefault()
          dialogRef.current?.close()
        }}
      >
        <div className="dialog-body">
          <div className="dialog-head">
            <h2>
              {base} / USDT
            </h2>
            <button type="button" onClick={() => dialogRef.current?.close()} aria-label="Fermer">
              ×
            </button>
          </div>

          {badge(cycle === '—' ? '—' : cycle)}
          <p>
            Fiche de décision · Ichimoku × RVOL · {timeframe}
            {detail?.strategy_version ? ` · ${detail.strategy_version}` : ''}
            {loading ? ' · chargement…' : ''}
          </p>
          {asOfNote && (
            <div className="notice blue" style={{ marginTop: 12 }}>
              {asOfNote}
            </div>
          )}
          {stale && (
            <div className="notice" style={{ marginTop: 12 }}>
              Données potentiellement périmées (stale / data_late).
            </div>
          )}
          {error && (
            <div className="notice" style={{ marginTop: 12, ...actionNoticeStyle(false) }}>
              {error}
            </div>
          )}
          {localNotice && (
            <div
              className="notice"
              style={{ marginTop: 12, ...actionNoticeStyle(localNotice.ok) }}
              role="status"
            >
              {localNotice.text}
            </div>
          )}

          <div className="segmented" role="tablist" aria-label="Onglets fiche">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                className={tab === t.id ? 'active' : ''}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>

          <div className="fiche-tab-panel">
            {tab === 'synthese' && (
              <>
                <div className="statline">
                  <span>Cycle</span>
                  <b>{badge(cycle === '—' ? '—' : cycle)}</b>
                </div>
                <div className="statline">
                  <span>Direction</span>
                  <b>
                    {pipeline
                      ? labelDirection(pipeline.direction)
                      : detail
                        ? labelDirection(detail.direction)
                        : '—'}
                  </b>
                </div>
                <div className="statline">
                  <span>Confiance</span>
                  <b>
                    {detail?.confidence != null
                      ? `${Math.round(detail.confidence * 100)} / 100`
                      : '— · confiance absente'}
                  </b>
                </div>
                <div className="statline">
                  <span>Verdict combiner</span>
                  <b>{detail ? labelDecision(detail.decision) : '—'}</b>
                </div>
                <div className="statline">
                  <span>Portes</span>
                  <b>
                    {detail?.pipeline?.decision
                      ? labelPipelineGate(
                          detail.pipeline.decision as PipelineGateLabel,
                        )
                      : '— · pipeline.decision absent'}
                  </b>
                </div>
                <p style={{ fontSize: 13, marginTop: 14, lineHeight: 1.6 }}>
                  {summary ?? (loading ? '…' : '— · résumé indisponible')}
                </p>
                <div className="statline">
                  <span>Invalidation</span>
                  <b>
                    {invalidation
                      ? labelReason(invalidation)
                      : '— · invalidation absente'}
                  </b>
                </div>
                <div className="statline">
                  <span>Version stratégie</span>
                  <b>{detail?.strategy_version ?? '— · strategy_version absente'}</b>
                </div>
                <div className="statline">
                  <span>Données au</span>
                  <b>{fmtTs(detail?.timestamp)}</b>
                </div>
              </>
            )}
            {tab === 'portes' && renderPortes()}
            {tab === 'preuves' && renderPreuves()}
            {tab === 'plan' && renderPlan()}
            {tab === 'historique' && renderHistorique()}
          </div>

          <div className="notice blue" style={{ marginTop: 20 }}>
            {alreadyOpen
              ? 'Position paper déjà ouverte sur ce symbole.'
              : 'Lecture moteur. Enregistrement journal ou ouverture paper au choix.'}
          </div>

          <button
            type="button"
            className="suggestion"
            style={{ width: '100%', marginTop: 16 }}
            disabled={alreadyOpen || paperBusy || paperConfirming || loading}
            title={paperDisabledReason ?? undefined}
            onClick={() => void startPaper()}
          >
            {alreadyOpen
              ? 'Déjà en portefeuille'
              : paperBusy
                ? 'Préparation paper…'
                : paperDisabledReason && !gatesPassed
                  ? 'Ouvrir en paper → (avis Attente)'
                  : 'Ouvrir en paper →'}
          </button>
          {paperDisabledReason && !alreadyOpen && (
            <p style={{ fontSize: 11, color: 'var(--muted)', marginTop: 8 }}>
              {paperDisabledReason} — l’ouverture paper reste possible (ticket manuel).
            </p>
          )}

          <div className="dialog-actions">
            <button
              type="button"
              onClick={() => {
                dialogRef.current?.close()
                navigate(`/app/market?symbol=${encodeURIComponent(symbol)}`)
              }}
            >
              Voir le graphique
            </button>
            <button
              type="button"
              className="primary"
              disabled={saveBusy || loading || !detail}
              onClick={() => void saveDecision()}
            >
              {saveBusy ? 'Enregistrement…' : 'Enregistrer la décision'}
            </button>
          </div>
        </div>
      </dialog>

      {paperConfirm && (
        <PaperConfirmSheet
          symbol={paperConfirm.symbol}
          timeframe={paperConfirm.timeframe}
          symbolLabel={displaySymbol(paperConfirm.symbol)}
          intent={paperConfirm.intent}
          confirming={paperConfirming}
          error={paperConfirmError}
          onConfirm={(order) => void executePaper(order)}
          onCancel={() => {
            if (!paperConfirming) setPaperConfirm(null)
          }}
        />
      )}
    </>
  )
}
