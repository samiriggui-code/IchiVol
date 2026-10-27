/**
 * Portefeuille — poste de trading premium (primitives iv-, voir src/theme/PREMIUM.md).
 * Données = engine (manquant → « — »).
 * Clôture paper : confirmation (PaperCloseConfirmSheet) → closePaperPosition.
 */

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { PaperCloseConfirmSheet } from '../components/PaperCloseConfirmSheet'
import { ChartIntelligencePanel } from '../components/chart-intelligence'
import { MtfPanel } from '../components/MtfPanel'
import { fmtUtc, storedMatrix } from '../lib/mtf'
import {
  concentrationFromPositions,
  drawdownFromCurve,
} from '../components/desk/deskMetrics'
import {
  closePaperPosition,
  getPaperActivity,
  getPaperOverview,
  listAccountPositions,
  loadAccountLots,
  type PaperOrderRow,
  type PaperPosition,
  type PaperOverview,
  type PaperOverviewPosition,
} from '../lib/paper'
import { labelPaperOrderReason, labelRiskRefusal } from '../lib/paperLabels'
import { VpValidationBadge } from '../components/VpValidationBadge'
import { isActionableBuySell } from '../lib/vpValidationCopy'
import { getRiskLock, type RiskLockState } from '../lib/riskLock'
import { displaySymbol } from '../lib/markets'
import { MAIN_PORTFOLIO_CODE, MAIN_PORTFOLIO_LABEL, MAIN_PORTFOLIO_SUMMARY } from '../lib/mainPortfolio'
import {
  activeRows,
  arbitrationFr,
  assetClassLabel,
  enginesFr,
  getPortfolioBreakdown,
  modeFr,
  sessionEventFr,
  universeByClass,
  type BreakdownStats,
  type PortfolioBreakdown,
} from '../lib/breakdown'
import { DECIDER_EXPLAIN, DECIDER_LABEL, deciderOf, type Decider } from '../lib/decider'
import './PortfolioPage.css'

type Tone = 'cyan' | 'amber' | 'mint' | 'buy' | 'sell' | 'muted'

function tag(text: string, tone: Tone = 'muted'): ReactNode {
  return <span className={`iv-tag is-${tone}`}>{text}</span>
}

/** Pastille « qui a décidé » au format premium (même libellé et même explication que DeciderBadge). */
function DeciderMark({ decider }: { decider: Decider }) {
  const cls = decider === 'eve' ? ' is-eve' : decider === 'manual' ? ' is-manual' : decider === 'engine_over_eve' ? ' is-vs' : ''
  return (
    <span
      className={`iv-decider${cls}`}
      title={DECIDER_EXPLAIN[decider]}
      aria-label={`${DECIDER_LABEL[decider]} : ${DECIDER_EXPLAIN[decider]}`}
    >
      <i aria-hidden="true" />
      {DECIDER_LABEL[decider]}
    </span>
  )
}

function signCls(n: number | null | undefined): string {
  return n == null || !Number.isFinite(n) ? '' : n > 0 ? 'pos' : n < 0 ? 'neg' : ''
}

function fmtEur(n: number | null | undefined, digits = 2): string {
  if (n == null || !Number.isFinite(n)) return '—'
  return (
    n.toLocaleString('fr-FR', {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    }) + ' €'
  )
}

function fmtSigned(n: number | null | undefined, digits = 2, suffix = ''): string {
  if (n == null || !Number.isFinite(n)) return '—'
  const sign = n > 0 ? '+' : n < 0 ? '−' : ''
  return `${sign}${Math.abs(n).toLocaleString('fr-FR', { minimumFractionDigits: digits, maximumFractionDigits: digits })}${suffix}`
}

function fmtPct(n: number | null | undefined, digits = 1, signed = false): string {
  if (n == null || !Number.isFinite(n)) return '—'
  const v = n * 100
  const sign = signed && v > 0 ? '+' : ''
  return `${sign}${v.toLocaleString('fr-FR', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })} %`
}

function fmtPctPoints(n: number | null | undefined, digits = 1): string {
  if (n == null || !Number.isFinite(n)) return '—'
  return `${n.toLocaleString('fr-FR', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })} %`
}

/** Valeur en euros découpée pour un KPI : partie entière, puis décimales et devise en petit. */
function KpiEur({ n, signed = false }: { n: number | null | undefined; signed?: boolean }) {
  if (n == null || !Number.isFinite(n)) return <>—</>
  const txt = signed ? fmtSigned(n, 2) : n.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  const cut = txt.lastIndexOf(',')
  return (
    <>
      {cut > 0 ? txt.slice(0, cut) : txt}
      <small>{cut > 0 ? `${txt.slice(cut)} €` : ' €'}</small>
    </>
  )
}

/** Jauge du Risk Kernel : libellé, valeur, barre (ambre au-delà de 80 %, rouge au plafond). */
function Meter({ label, value, pct }: { label: string; value: string; pct: number | null }) {
  const width = pct == null || !Number.isFinite(pct) ? 0 : Math.max(0, Math.min(100, pct))
  const tone = pct != null && pct >= 100 ? ' is-sell' : pct != null && pct >= 80 ? ' is-amber' : ''
  return (
    <div className="pf-meter">
      <span className="pf-meter-t">{label}</span>
      <span className="pf-meter-v">{value}</span>
      <div className={`iv-bar${tone}`}>
        <i style={{ width: `${width}%` }} />
      </div>
    </div>
  )
}

function orderReasonFr(reason: string | null | undefined): string {
  return labelPaperOrderReason(reason)
}

function rMultiple(p: PaperOverviewPosition): number | null {
  const entry = p.entry_price
  const stop = p.stop_price
  const last = p.current_price
  if (entry == null || stop == null || last == null) return null
  const risk = p.direction === 'SHORT' ? stop - entry : entry - stop
  if (!Number.isFinite(risk) || risk <= 0) return null
  const move = p.direction === 'SHORT' ? entry - last : last - entry
  return move / risk
}

function stopDistance(p: PaperOverviewPosition): number | null {
  if (p.current_price == null || p.stop_price == null || !p.current_price) return null
  return Math.abs(p.current_price - p.stop_price) / p.current_price
}

/** Courbe de capital en aire : la série du moteur telle quelle, axe à droite (bas, haut, dernier). */
function EquityArea({ points }: { points: { t: string; equity: number }[] }) {
  const ys = points.map((p) => p.equity).filter((n) => Number.isFinite(n) && n > 0)
  if (ys.length < 2) {
    return <div className="iv-empty pf-chart-empty">Pas encore assez de points pour tracer la courbe de capital.</div>
  }
  const min = Math.min(...ys)
  const max = Math.max(...ys)
  const span = max - min || 1
  const w = 800
  const h = 200
  const pad = 10
  const yOf = (y: number) => h - pad - ((y - min) / span) * (h - 2 * pad)
  const pts = ys.map((y, i) => [(i / (ys.length - 1)) * w, yOf(y)] as const)
  const line = pts.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const area = `${line} L${w},${h} L0,${h} Z`
  const last = ys[ys.length - 1]!
  const ticks = [max, min + span * 0.75, min + span * 0.5, min + span * 0.25, min]
  const fmt = (n: number) => n.toLocaleString('fr-FR', { maximumFractionDigits: 0 })
  return (
    <div className="pf-chart">
      <svg className="pf-chart-svg" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" role="img" aria-label="Courbe de capital">
        <defs>
          <linearGradient id="pf-area-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" className="pf-area-stop-a" />
            <stop offset="100%" className="pf-area-stop-b" />
          </linearGradient>
        </defs>
        {[0.25, 0.5, 0.75].map((f) => (
          <line key={f} className="pf-chart-grid" x1="0" x2={w} y1={pad + f * (h - 2 * pad)} y2={pad + f * (h - 2 * pad)} vectorEffect="non-scaling-stroke" />
        ))}
        <path d={area} fill="url(#pf-area-fill)" />
        <path d={line} className="pf-chart-line" vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="pf-chart-axis" aria-hidden="true">
        {ticks.map((t, i) => (
          <span key={i}>{fmt(t)}</span>
        ))}
      </div>
      <span className="pf-chart-last" style={{ top: `${(yOf(last) / h) * 100}%` }}>
        {fmt(last)}
      </span>
    </div>
  )
}

function fmtPx(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return '—'
  return n.toLocaleString('fr-FR', { maximumFractionDigits: 6 })
}

function fmtTime(iso: string | null | undefined): string {
  if (!iso || Number.isNaN(Date.parse(iso))) return '—'
  return new Date(iso).toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

/** Tableau de performance (par décideur ou par classe d'actifs), chiffres du moteur (/breakdown). */
function PerfTable<T extends BreakdownStats>({
  rows,
  label,
  first,
}: {
  rows: T[]
  label: string
  first: (row: T) => ReactNode
}) {
  return (
    <div className="iv-card-body is-flush iv-table-wrap">
      <table className="iv-table is-compact">
        <thead>
          <tr>
            <th>{label}</th>
            <th className="n">Trades</th>
            <th className="n">Réussite</th>
            <th className="n">Net</th>
            <th className="n">Gain moy. / perte moy.</th>
            <th className="n">Frais</th>
            <th className="n">En cours</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td>{first(r)}</td>
              <td className="n">{r.trades > 0 ? `${r.trades} · ${r.wins} / ${r.losses}` : '0'}</td>
              <td className="n">{r.trades > 0 && r.win_rate != null ? fmtPct(r.win_rate, 0) : '—'}</td>
              <td className={`n ${signCls(r.net)}`}>{r.trades > 0 ? fmtSigned(r.net, 2, ' €') : '—'}</td>
              <td className="n">
                {r.avg_win != null ? fmtEur(r.avg_win, 2) : '—'} / {r.avg_loss != null ? fmtEur(r.avg_loss, 2) : '—'}
              </td>
              <td className="n dim">{r.trades > 0 ? fmtEur(r.fees, 2) : '—'}</td>
              <td className="n">{r.open}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Filtres et fenêtre de session notés sur le lot (le compte unique les suit en observation, sans bloquer). */
function ObservedFilters({ signal }: { signal: Record<string, unknown> | null | undefined }) {
  const f = (signal?.filters_observed ?? null) as
    | {
        would_block?: boolean
        structure_blocked?: boolean
        fibonacci_blocked?: boolean
        context_blocked?: boolean
        block_source?: string | null
        block_reason?: string | null
      }
    | null
  const event = signal?.decision_event
  if (!f && signal?.decision_event === undefined) return null
  const eventText = sessionEventFr(event)
  const yes = (b: boolean | undefined) => (b ? <span className="neg">aurait bloqué</span> : <span className="ok">passe</span>)
  return (
    <div className="pf-fiche-grid">
      {f ? (
        <>
          <div className="iv-row">
            <span>Filtres (observation)</span>
            <span className="iv-row-v">
              {f.would_block ? (
                <span className="neg">
                  auraient refusé{f.block_source ? ` · ${f.block_source}` : ''}
                  {f.block_reason ? ` (${f.block_reason})` : ''}
                </span>
              ) : (
                <span className="ok">aucun refus</span>
              )}
            </span>
          </div>
          <div className="iv-row">
            <span>Structure</span>
            <span className="iv-row-v">{yes(f.structure_blocked)}</span>
          </div>
          <div className="iv-row">
            <span>Fibonacci</span>
            <span className="iv-row-v">{yes(f.fibonacci_blocked)}</span>
          </div>
          <div className="iv-row">
            <span>Contexte (RSI, flux, régime)</span>
            <span className="iv-row-v">{yes(f.context_blocked)}</span>
          </div>
        </>
      ) : null}
      <div className="iv-row">
        <span>Session à l’entrée</span>
        <span className="iv-row-v">{eventText}</span>
      </div>
    </div>
  )
}

/** Trades clôturés chargés par page dans « Historique des trades ». */
const HISTORY_PAGE = 30

export function PortfolioPage() {
  const [searchParams] = useSearchParams()
  const tabParam = searchParams.get('tab')

  // `?tab=positions|risque|ordres` (notifications, Desk, anciennes routes) : on amène à la carte correspondante.
  useEffect(() => {
    if (!tabParam) return
    const id = { positions: 'pf-positions', risque: 'pf-risque', ordres: 'pf-ordres' }[tabParam]
    if (!id) return
    const t = window.setTimeout(() => document.getElementById(id)?.scrollIntoView({ block: 'start', behavior: 'smooth' }), 150)
    return () => window.clearTimeout(t)
  }, [tabParam])
  // Un seul portefeuille paper (ICHIVOL_MAIN_V1) : un ancien lien `?pf=CODE` est ignoré.
  const code = MAIN_PORTFOLIO_CODE
  const [overview, setOverview] = useState<PaperOverview | null>(null)
  const [orders, setOrders] = useState<PaperOrderRow[]>([])
  const [lock, setLock] = useState<RiskLockState | null>(null)
  /** Qui a décidé chaque lot (moteur seul, Ève, manuel), pour étiqueter aussi les ordres. */
  const [deciderByPosition, setDeciderByPosition] = useState<Record<string, Decider>>({})
  const [breakdown, setBreakdown] = useState<PortfolioBreakdown | null>(null)
  /** Trades clôturés du compte, paginés par le moteur (/paper/positions?portfolio_code=…). */
  const [history, setHistory] = useState<PaperPosition[]>([])
  const [historyTotal, setHistoryTotal] = useState(0)
  const [historyBusy, setHistoryBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [fiche, setFiche] = useState<PaperOverviewPosition | null>(null)
  const [closeTarget, setCloseTarget] = useState<PaperOverviewPosition | null>(null)
  const [closeConfirming, setCloseConfirming] = useState(false)
  const [closeError, setCloseError] = useState<string | null>(null)
  const closeLock = useRef(false)
  const [chartTab, setChartTab] = useState<'courbe' | 'allocation' | 'concentration'>('courbe')

  const load = useCallback(async () => {
    setLoading(true)
    void loadAccountLots()
      .then((lots) => setDeciderByPosition(Object.fromEntries(lots.map((p) => [p.id, deciderOf(p)]))))
      .catch(() => undefined)
    void listAccountPositions({ code, status: 'CLOSED', limit: HISTORY_PAGE })
      .then((page) => {
        setHistory(page.positions)
        setHistoryTotal(page.total)
      })
      .catch(() => undefined)
    void getPortfolioBreakdown(code)
      .then(setBreakdown)
      .catch(() => setBreakdown(null))
    try {
      const [ov, lk, activity] = await Promise.all([
        getPaperOverview(code),
        getRiskLock(code).catch(() => null),
        getPaperActivity(code, 12).catch(() => [] as PaperOrderRow[]),
      ])
      setOverview(ov)
      setLock(lk)
      setOrders(activity)
    } catch {
      setOverview(null)
    } finally {
      setLoading(false)
    }
  }, [code])

  useEffect(() => {
    void load()
  }, [load])

  async function loadMoreHistory() {
    setHistoryBusy(true)
    try {
      const page = await listAccountPositions({ code, status: 'CLOSED', limit: HISTORY_PAGE, offset: history.length })
      setHistoryTotal(page.total)
      setHistory((prev) => {
        const seen = new Set(prev.map((p) => p.id))
        return [...prev, ...page.positions.filter((p) => !seen.has(p.id))]
      })
    } catch {
      /* garder l'historique actuel */
    } finally {
      setHistoryBusy(false)
    }
  }

  useEffect(() => {
    const wanted = searchParams.get('symbol')?.toUpperCase()
    if (!wanted || !overview) return
    const hit = (overview.positions ?? []).find(
      (p) => p.symbol.toUpperCase() === wanted && String(p.status).toUpperCase() === 'OPEN',
    )
    if (hit) setFiche(hit)
  }, [searchParams, overview])

  const acct = overview?.account
  const risk = overview?.risk
  const positions = useMemo(
    () => (overview?.positions ?? []).filter((p) => String(p.status).toUpperCase() === 'OPEN'),
    [overview?.positions],
  )
  const concentration = useMemo(
    () => concentrationFromPositions(positions),
    [positions],
  )
  const positionsBadge =
    positions.length === 0
      ? '—'
      : positions.length === 1
        ? '1 POSITION'
        : `${positions.length} POSITIONS`
  const dd = drawdownFromCurve(overview?.equity_curve ?? [], acct?.equity)
  /** Drawdown actuel : celui du moteur (/breakdown) s'il répond, sinon calculé sur la courbe affichée. */
  const ddNow = breakdown?.drawdown.current_pct != null ? -Math.abs(breakdown.drawdown.current_pct) : dd
  const investedPct =
    acct && acct.equity > 0 ? Math.min(100, Math.max(0, (acct.invested / acct.equity) * 100)) : null

  const riskPass =
    lock == null
      ? null
      : !lock.entries_blocked && !lock.daily_loss_locked && !lock.kill_switch_armed

  async function executeClose() {
    if (!closeTarget?.id || closeLock.current) return
    closeLock.current = true
    setCloseConfirming(true)
    setCloseError(null)
    try {
      await closePaperPosition(closeTarget.id)
      setCloseTarget(null)
      await load()
    } catch (err: unknown) {
      setCloseError(err instanceof Error ? err.message : 'Clôture impossible')
    } finally {
      setCloseConfirming(false)
      closeLock.current = false
    }
  }

  const currentLabel = MAIN_PORTFOLIO_LABEL
  const pnlTotal = acct ? acct.equity - acct.initial_cash : null
  const dayBase = acct?.day_change != null && acct.equity - acct.day_change > 0 ? acct.equity - acct.day_change : null
  const dayPct = acct?.day_change != null && dayBase ? acct.day_change / dayBase : null
  const costs = overview?.costs
  const winRate = costs && costs.closed_trades > 0 ? costs.wins / costs.closed_trades : null
  const avgWin = costs && costs.wins > 0 ? costs.sum_wins / costs.wins : null
  const avgLoss = costs && costs.losses > 0 ? costs.sum_losses / costs.losses : null
  const payoff = avgWin != null && avgLoss != null && avgLoss !== 0 ? Math.abs(avgWin / avgLoss) : null
  const notionalOpen = positions.reduce<number | null>((s, p) => {
    const v =
      p.market_value ??
      (p.current_price != null && p.qty != null ? p.current_price * Math.abs(p.qty) : p.notional ?? null)
    return v == null ? s : (s ?? 0) + v
  }, null)
  const refusals = risk?.recent_refusals ?? []

  return (
    <div className="pf-page">
      <div className="iv-ph">
        <div>
          <div className="iv-meta">Portefeuille · paper · ordres simulés, aucun envoyé à l’extérieur</div>
          <h1>Portefeuille</h1>
          <p>
            {MAIN_PORTFOLIO_SUMMARY} Les ordres sont simulés ici, aucun n’est envoyé à un courtier.
          </p>
        </div>
        <div className="iv-ph-act">
          {riskPass === true
            ? tag('Ouvert aux entrées', 'mint')
            : riskPass === false
              ? tag('Entrées bloquées', 'sell')
              : null}
          <span className="iv-chip">
            Risk Kernel ·{' '}
            <b className={riskPass === true ? 'ok' : riskPass === false ? 'neg' : 'dim'}>
              {riskPass === true ? 'PASSE' : riskPass === false ? 'BLOQUÉ' : '—'}
            </b>
          </span>
          {tag(`${MAIN_PORTFOLIO_LABEL} · paper`, 'amber')}
        </div>
      </div>


      <div className="iv-kpis pf-kpis">
        <div className="iv-kpi">
          <div className="iv-kpi-k">Capital de départ</div>
          <div className="iv-kpi-v">
            <KpiEur n={acct?.initial_cash} />
          </div>
          <div className="iv-kpi-s">{MAIN_PORTFOLIO_LABEL} · portefeuille unique</div>
        </div>
        <div className="iv-kpi">
          <div className="iv-kpi-k">Valeur</div>
          <div className="iv-kpi-v">
            <KpiEur n={acct?.equity} />
          </div>
          <div className="iv-kpi-s">{acct ? `dont cash ${fmtEur(acct.cash, 2)}` : '—'}</div>
        </div>
        <div className="iv-kpi">
          <div className="iv-kpi-k">Gain / perte</div>
          <div className={`iv-kpi-v ${signCls(pnlTotal)}`}>{fmtSigned(pnlTotal, 2)}</div>
          <div className="iv-kpi-s">
            {acct ? `réalisé ${fmtSigned(acct.realized_pnl, 2)} · latent ${fmtSigned(acct.unrealized_pnl, 2)}` : '—'}
          </div>
        </div>
        <div className="iv-kpi">
          <div className="iv-kpi-k">Variation du jour</div>
          <div className={`iv-kpi-v ${signCls(acct?.day_change)}`}>{fmtSigned(acct?.day_change, 2)}</div>
          <div className={`iv-kpi-s ${signCls(dayPct)}`}>{dayPct != null ? fmtPct(dayPct, 2, true) : '—'}</div>
        </div>
        <div className="iv-kpi">
          <div className="iv-kpi-k">Exposition</div>
          <div className="iv-kpi-v">
            <KpiEur n={acct?.invested} />
          </div>
          <div className="iv-kpi-s">{investedPct != null ? `${fmtPctPoints(investedPct, 1)} du capital` : '—'}</div>
        </div>
        <div className="iv-kpi">
          <div className="iv-kpi-k">Drawdown</div>
          <div className={`iv-kpi-v ${ddNow != null && ddNow < 0 ? 'neg' : ''}`}>{ddNow != null ? fmtPct(ddNow, 1, true) : '—'}</div>
          <div className="iv-kpi-s">
            {breakdown?.drawdown.max_pct != null ? `max ${fmtPct(-Math.abs(breakdown.drawdown.max_pct), 1, true)}` : 'depuis le plus haut'}
          </div>
        </div>
        <div className="iv-kpi">
          <div className="iv-kpi-k">Taux de réussite</div>
          <div className="iv-kpi-v">{winRate != null ? fmtPct(winRate, 1) : '—'}</div>
          <div className="iv-kpi-s">{costs ? `${costs.closed_trades} trades clôturés` : '—'}</div>
        </div>
        <div className="iv-kpi">
          <div className="iv-kpi-k">Gain / perte moy.</div>
          <div className="iv-kpi-v">
            {payoff != null ? (
              <>
                {payoff.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                <small> ×</small>
              </>
            ) : (
              '—'
            )}
          </div>
          <div className="iv-kpi-s">
            <span className={signCls(avgWin)}>{fmtSigned(avgWin, 2)}</span> /{' '}
            <span className={signCls(avgLoss)}>{fmtSigned(avgLoss, 2)}</span>
          </div>
        </div>
      </div>


      <div className="iv-grid pf-section">
        <section className="iv-card iv-s8 iv-m-s12 pf-chart-card">
          <div className="iv-card-head">
            <div className="iv-card-tabs" role="tablist" aria-label="Capital">
              <button
                type="button"
                role="tab"
                aria-selected={chartTab === 'courbe'}
                className={`iv-card-tab${chartTab === 'courbe' ? ' is-on' : ''}`}
                onClick={() => setChartTab('courbe')}
              >
                Courbe de capital
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={chartTab === 'allocation'}
                className={`iv-card-tab${chartTab === 'allocation' ? ' is-on' : ''}`}
                onClick={() => setChartTab('allocation')}
              >
                Allocation
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={chartTab === 'concentration'}
                className={`iv-card-tab${chartTab === 'concentration' ? ' is-on' : ''}`}
                onClick={() => setChartTab('concentration')}
              >
                Concentration
              </button>
            </div>
            <div className="iv-card-tools">{currentLabel}</div>
          </div>
          <div className="iv-card-body">
            {chartTab === 'courbe' ? (
              <EquityArea points={overview?.equity_curve ?? []} />
            ) : chartTab === 'allocation' ? (
              <div className="pf-alloc">
                <div
                  className="pf-donut"
                  style={
                    investedPct != null
                      ? { background: `conic-gradient(var(--cyan) 0 ${investedPct}%, var(--track-bg) ${investedPct}% 100%)` }
                      : undefined
                  }
                >
                  <span>
                    <b>{investedPct != null ? fmtPctPoints(investedPct, 1) : '—'}</b>
                    <small>engagé</small>
                  </span>
                </div>
                <div className="pf-alloc-rows">
                  <div className="iv-row">
                    <span>Capital de départ</span>
                    <span className="iv-row-v">{acct ? fmtEur(acct.initial_cash, 2) : '—'}</span>
                  </div>
                  <div className="iv-row">
                    <span>Disponible (réserve non engagée)</span>
                    <span className="iv-row-v">{acct ? fmtEur(acct.cash, 2) : '—'}</span>
                  </div>
                  <div className="iv-row">
                    <span>P&amp;L réalisé</span>
                    <span className={`iv-row-v ${signCls(acct?.realized_pnl)}`}>{acct ? fmtEur(acct.realized_pnl, 2) : '—'}</span>
                  </div>
                  <div className="iv-row">
                    <span>P&amp;L latent</span>
                    <span className={`iv-row-v ${signCls(acct?.unrealized_pnl)}`}>{acct ? fmtEur(acct.unrealized_pnl, 2) : '—'}</span>
                  </div>
                  <div className="iv-row">
                    <span>Commissions</span>
                    <span className="iv-row-v">{costs ? fmtEur(costs.commissions, 2) : '—'}</span>
                  </div>
                  <div className="iv-row">
                    <span>Spread et slippage</span>
                    <span className="iv-row-v">{costs ? fmtEur(costs.spread_slippage, 2) : '—'}</span>
                  </div>
                  <div className="iv-row">
                    <span>Financement</span>
                    <span className="iv-row-v">{costs ? fmtEur(costs.financing, 2) : '—'}</span>
                  </div>
                  <div className="iv-row">
                    <span>Trades clôturés</span>
                    <span className="iv-row-v">
                      {costs ? `${costs.closed_trades} · ${costs.wins} gains / ${costs.losses} pertes` : '—'}
                    </span>
                  </div>
                  {costs?.note ? <p className="iv-note pf-small">{costs.note}</p> : null}
                </div>
              </div>
            ) : concentration.length === 0 ? (
              <p className="iv-note pf-small">
                Aucune position ouverte : rien à concentrer. Dès qu’un lot paper est ouvert, tu vois ici la part de chaque
                symbole dans l’exposition (notional / capital engagé). Le Risk Kernel refuse un nouvel actif si le plafond
                d’exposition symbole ou le cash ne suit pas.
              </p>
            ) : (
              <>
                {concentration.map((c) => (
                  <Meter key={c.symbol} label={c.symbol} value={`${fmtPctPoints(c.pct, 1)} de l’exposition`} pct={c.pct} />
                ))}
                <p className="iv-note pf-small">
                  {concentration.length} ligne{concentration.length > 1 ? 's' : ''} ouverte
                  {concentration.length > 1 ? 's' : ''}. Le broker paper n’ajoute pas une position si le cash ou le plafond
                  de risque ne suit pas.
                </p>
              </>
            )}
          </div>
        </section>

        <section className="iv-card iv-glow iv-s4 iv-m-s12" id="pf-risque">
          <div className="iv-card-head">
            <div className="iv-card-tabs">
              <span className="iv-card-tab is-on">Risk Kernel</span>
            </div>
            <div className="iv-card-tools">Limites</div>
          </div>
          <div className="iv-card-body">
            <div className="pf-kernel">
              <span className={`pf-kernel-v ${riskPass === true ? 'ok' : riskPass === false ? 'neg' : 'dim'}`}>
                {riskPass === true ? 'PASSE' : riskPass === false ? 'BLOQUÉ' : '—'}
              </span>
              <span className="pf-kernel-t">
                {riskPass === true
                  ? 'Les nouvelles entrées paper sont autorisées.'
                  : riskPass === false
                    ? 'Entrées bloquées (arrêt d’urgence ou perte journalière).'
                    : 'État du verrou indisponible.'}
                <br />
                {risk
                  ? risk.open_positions === 0
                    ? 'Aucune position ouverte — les jauges à 0 sont normales.'
                    : `${risk.open_positions} position${risk.open_positions === 1 ? '' : 's'} sous surveillance`
                  : '—'}
              </span>
            </div>
            <Meter
              label="Risque ouvert (stop → entrée)"
              value={
                risk?.open_risk_amount != null
                  ? `${fmtEur(risk.open_risk_amount, 2)}${risk.open_risk_pct != null ? ` · ${fmtPct(risk.open_risk_pct, 2)}` : ''}`
                  : '—'
              }
              pct={risk?.open_risk_pct != null && risk.max_open_risk_pct ? (risk.open_risk_pct / risk.max_open_risk_pct) * 100 : null}
            />
            <Meter
              label="Plafond risque ouvert"
              value={
                risk?.open_risk_pct != null && risk.max_open_risk_pct != null
                  ? `${fmtPct(risk.open_risk_pct, 1).replace(' %', '')} / ${fmtPct(risk.max_open_risk_pct, 0)}`
                  : risk?.max_open_risk_pct != null
                    ? `0 / ${fmtPct(risk.max_open_risk_pct, 0)}`
                    : '—'
              }
              pct={risk?.open_risk_pct != null && risk.max_open_risk_pct ? (risk.open_risk_pct / risk.max_open_risk_pct) * 100 : null}
            />
            <Meter
              label="Exposition / capital"
              value={investedPct != null ? `${fmtPctPoints(investedPct, 1)} engagé` : '—'}
              pct={investedPct}
            />
            <Meter
              label="Positions simultanées"
              value={risk ? `${risk.open_positions} / ${risk.max_open_positions}` : '—'}
              pct={risk && risk.max_open_positions > 0 ? (risk.open_positions / risk.max_open_positions) * 100 : null}
            />
            <div className="pf-kernel-rows">
              {lock ? (
                <>
                  <div className="iv-row">
                    <span>Arrêt d’urgence</span>
                    <span className={`iv-row-v ${lock.kill_switch_armed ? 'neg' : 'ok'}`}>
                      {lock.kill_switch_armed ? 'armé (entrées coupées)' : 'désarmé'}
                    </span>
                  </div>
                  <div className="iv-row">
                    <span>Perte du jour</span>
                    <span className={`iv-row-v ${lock.daily_loss_locked ? 'neg' : 'ok'}`}>
                      {lock.daily_loss_locked ? 'plafond atteint' : 'sous le plafond'}
                    </span>
                  </div>
                  <div className="iv-row">
                    <span>Entrées</span>
                    <span className={`iv-row-v ${lock.entries_blocked ? 'neg' : 'ok'}`}>
                      {lock.entries_blocked ? 'bloquées' : 'ouvertes'}
                    </span>
                  </div>
                </>
              ) : null}
              <div className="iv-row">
                <span>Ordres refusés par le risque</span>
                <span className="iv-row-v">{risk ? (refusals.length === 0 ? 'aucun récent' : `${refusals.length} récent${refusals.length > 1 ? 's' : ''}`) : '—'}</span>
              </div>
            </div>
            <p className="iv-note pf-small">
              Garde-fou du <b>moteur</b> : avant toute ouverture, il vérifie shorts, cash, plafonds, arrêt d’urgence et perte
              du jour. Ce n’est pas un score de marché — c’est l’autorisation d’entrer.
            </p>
          </div>
          <div className="iv-card-foot">
            Détail des seuils
            <Link to="/app/settings">Paramètres →</Link>
          </div>
        </section>
      </div>

      <div className="iv-grid pf-section">
        <section className="iv-card iv-s12" id="pf-positions">
          <div className="iv-card-head">
            <div className="iv-card-tabs">
              <span className="iv-card-tab is-on">Positions ouvertes</span>
            </div>
            <div className="iv-card-tools">
              {positionsBadge}
              {notionalOpen != null ? ` · notionnel ${fmtEur(notionalOpen, 0)}` : ''}
            </div>
          </div>
          {positions.length === 0 ? (
            <div className="iv-empty">{loading ? 'Chargement…' : 'Aucune position ouverte'}</div>
          ) : (
            <div className="iv-card-body is-flush iv-table-wrap">
              <table className="iv-table">
                <thead>
                  <tr>
                    <th>Actif</th>
                    <th>Sens</th>
                    <th>Décideur</th>
                    <th className="n">Qté</th>
                    <th className="n">Entrée</th>
                    <th className="n">Prix actuel</th>
                    <th className="n">Stop</th>
                    <th className="n">Objectif</th>
                    <th className="n">Distance au stop</th>
                    <th className="n">P&amp;L latent</th>
                    <th className="n">R</th>
                    <th>
                      <span className="pf-sr">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {positions.map((p: PaperOverviewPosition) => {
                    const pnl = p.unrealized_pnl
                    const perf = p.unrealized_pct
                    const r = rMultiple(p)
                    const dist = stopDistance(p)
                    const engaged =
                      p.market_value ??
                      (p.current_price != null && p.qty != null ? p.current_price * Math.abs(p.qty) : p.notional ?? null)
                    const strat =
                      p.timeframe != null
                        ? `Ichimoku × RVOL · ${String(p.timeframe).toUpperCase()}${engaged != null ? ` · ${fmtEur(engaged, 0)} engagés` : ''}`
                        : undefined
                    const selected = fiche != null && fiche.id === p.id
                    return (
                      <tr
                        key={p.id ?? p.symbol}
                        className={`pf-click${selected ? ' is-selected' : ''}`}
                        tabIndex={0}
                        title={strat}
                        onClick={() => setFiche(p)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            setFiche(p)
                          }
                        }}
                      >
                        <td className="sym">
                          {displaySymbol(p.symbol)}
                          <small>{String(p.timeframe ?? '').toUpperCase()}</small>
                        </td>
                        <td>
                          <span className={`iv-side ${p.direction === 'SHORT' ? 'is-short' : 'is-long'}`}>
                            {p.direction === 'SHORT' ? 'VENTE' : 'ACHAT'}
                          </span>
                        </td>
                        <td>
                          <DeciderMark decider={deciderOf(p)} />
                        </td>
                        <td className="n">{p.qty != null ? fmtPx(p.qty) : '—'}</td>
                        <td className="n">{fmtPx(p.entry_price)}</td>
                        <td className="n">
                          {fmtPx(p.current_price)}
                          {p.mark_stale ? (
                            <span className="pf-stale" title="Cours périmé : la dernière cotation est ancienne">
                              {' '}
                              {tag('Cours périmé', 'amber')}
                            </span>
                          ) : null}
                        </td>
                        <td className="n neg">{fmtPx(p.stop_price)}</td>
                        <td className="n ok">{fmtPx(p.take_profit_price)}</td>
                        <td className="n">{dist != null ? fmtPct(dist, 2) : '—'}</td>
                        <td className={`n ${signCls(pnl)}`}>
                          {fmtSigned(pnl, 2, ' €')}
                          {perf != null ? <span className="pf-sub"> · {fmtPct(perf, 2, true)}</span> : null}
                        </td>
                        <td className={`n ${signCls(r)}`}>{r == null ? '—' : fmtSigned(r, 2)}</td>
                        <td className="pf-act">
                          {p.id ? (
                            <button
                              type="button"
                              className="iv-btn iv-btn--sm"
                              onClick={(e) => {
                                e.stopPropagation()
                                setCloseError(null)
                                setCloseTarget(p)
                              }}
                            >
                              Clôturer
                            </button>
                          ) : null}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
          <div className="iv-card-foot">
            Stop et objectif surveillés en continu · touchez une ligne pour sa fiche
          </div>
        </section>
      </div>

      <div className="iv-grid pf-section">
        <section className="iv-card iv-s6 iv-m-s12" id="pf-decideurs">
          <div className="iv-card-head">
            <div className="iv-card-tabs">
              <span className="iv-card-tab is-on">Performance par décideur</span>
            </div>
            <div className="iv-card-tools">Net de frais · moteur</div>
          </div>
          {breakdown ? (
            <PerfTable rows={breakdown.by_decider} label="Décideur" first={(r) => <DeciderMark decider={r.decider} />} />
          ) : (
            <div className="iv-empty">{loading ? 'Chargement…' : 'Bilan indisponible.'}</div>
          )}
          <div className="iv-card-foot">Qui a décidé : Ève, moteur contre Ève, moteur seul, ou vous</div>
        </section>
        <section className="iv-card iv-s6 iv-m-s12" id="pf-classes">
          <div className="iv-card-head">
            <div className="iv-card-tabs">
              <span className="iv-card-tab is-on">Performance par classe d’actifs</span>
            </div>
            <div className="iv-card-tools">Net de frais · moteur</div>
          </div>
          {breakdown && activeRows(breakdown.by_asset_class).length > 0 ? (
            <PerfTable rows={activeRows(breakdown.by_asset_class)} label="Classe" first={(r) => assetClassLabel(r)} />
          ) : (
            <div className="iv-empty">
              {breakdown ? 'Aucun trade pour l’instant.' : loading ? 'Chargement…' : 'Bilan indisponible.'}
            </div>
          )}
          <div className="iv-card-foot">Crypto, forex, métaux, indices, énergie, futures</div>
        </section>
      </div>

      <div className="iv-grid pf-section">
        <section className="iv-card iv-s12" id="pf-historique">
          <div className="iv-card-head">
            <div className="iv-card-tabs">
              <span className="iv-card-tab is-on">Historique des trades</span>
            </div>
            <div className="iv-card-tools">
              {historyTotal ? `${history.length} sur ${historyTotal} clôturés` : '—'}
            </div>
          </div>
          {history.length === 0 ? (
            <div className="iv-empty">{loading ? 'Chargement…' : 'Aucun trade clôturé sur ce compte pour l’instant.'}</div>
          ) : (
            <div className="iv-card-body is-flush iv-table-wrap">
              <table className="iv-table is-compact">
                <thead>
                  <tr>
                    <th>Sortie</th>
                    <th>Actif</th>
                    <th>Sens</th>
                    <th>Décideur</th>
                    <th className="n">Entrée</th>
                    <th className="n">Sortie</th>
                    <th>Motif</th>
                    <th className="n">Résultat net</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((p) => (
                    <tr key={p.id}>
                      <td className="mono dim">{fmtTime(p.exit_time)}</td>
                      <td className="sym">
                        {displaySymbol(p.symbol)}
                        <small>{String(p.timeframe ?? '').toUpperCase()}</small>
                      </td>
                      <td>
                        <span className={`iv-side ${p.direction === 'SHORT' ? 'is-short' : 'is-long'}`}>
                          {p.direction === 'SHORT' ? 'VENTE' : 'ACHAT'}
                        </span>
                      </td>
                      <td>
                        <DeciderMark decider={deciderOf(p)} />
                      </td>
                      <td className="n">{fmtPx(p.entry_price)}</td>
                      <td className="n">{fmtPx(p.exit_price)}</td>
                      <td className="dim">{orderReasonFr(p.exit_reason) || '—'}</td>
                      <td className={`n ${signCls(p.realized_pnl)}`}>
                        {fmtSigned(p.realized_pnl, 2, ' €')}
                        {p.pnl_pct != null ? <span className="pf-sub"> · {fmtPct(p.pnl_pct, 2, true)}</span> : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {historyTotal > history.length ? (
            <div className="iv-card-foot">
              <span>Plus récents d’abord</span>
              <button type="button" className="iv-btn iv-btn--sm" disabled={historyBusy} onClick={() => void loadMoreHistory()}>
                {historyBusy ? 'Chargement…' : `Afficher ${Math.min(HISTORY_PAGE, historyTotal - history.length)} de plus`}
              </button>
            </div>
          ) : null}
        </section>
      </div>

      <div className="iv-grid pf-section">
        <section className="iv-card iv-s7 iv-m-s12" id="pf-ordres">
          <div className="iv-card-head">
            <div className="iv-card-tabs">
              <span className="iv-card-tab is-on">Historique des ordres</span>
            </div>
            <div className="iv-card-tools">{orders.length ? `${orders.length} derniers` : '—'}</div>
          </div>
          {orders.length === 0 ? (
            <div className="iv-empty">{loading ? 'Chargement…' : 'Aucun ordre paper'}</div>
          ) : (
            <div className="iv-card-body is-flush iv-table-wrap">
              <table className="iv-table is-compact">
                <thead>
                  <tr>
                    <th>Heure</th>
                    <th>Actif</th>
                    <th>Sens</th>
                    <th>Décideur</th>
                    <th className="n">Qté</th>
                    <th className="n">Prix exécuté</th>
                    <th className="n">Frais</th>
                    <th>Statut</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.map((o) => {
                    const reason = orderReasonFr(o.reason)
                    const filled = o.status === 'FILLED'
                    return (
                      <tr key={o.id}>
                        <td className="mono dim">{fmtTime(o.time)}</td>
                        <td className="sym">
                          {displaySymbol(o.symbol)}
                          <small>{String(o.timeframe).toUpperCase()}</small>
                        </td>
                        <td className={o.side === 'SELL' ? 'neg' : 'pos'}>{o.side === 'SELL' ? 'Vente' : 'Achat'}</td>
                        <td>
                          {o.position_id && deciderByPosition[o.position_id] ? (
                            <DeciderMark decider={deciderByPosition[o.position_id]!} />
                          ) : (
                            <span className="dim">—</span>
                          )}
                        </td>
                        <td className="n">{fmtPx(o.qty)}</td>
                        <td className="n">{fmtPx(o.filled_price)}</td>
                        <td className="n dim">{fmtEur(o.fee, 2)}</td>
                        <td>
                          {tag(filled ? 'Exécuté' : o.status, filled ? 'mint' : /REJ|REFUS|CANCEL/i.test(o.status) ? 'sell' : 'muted')}
                          {reason ? <span className="pf-reason">{reason}</span> : null}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <div className="iv-s5 iv-m-s12 pf-stack">
          <section className="iv-card">
            <div className="iv-card-head">
              <div className="iv-card-tabs">
                <span className="iv-card-tab is-on">Ordres refusés par le risque</span>
              </div>
              <div className="iv-card-tools">{refusals.length ? `${Math.min(refusals.length, 5)} derniers` : ''}</div>
            </div>
            {refusals.length === 0 ? (
              <div className="iv-empty">
                {risk
                  ? 'Aucun refus récent. Les refus (ex. vente à découvert interdite) apparaissent ici quand le journal en a.'
                  : '—'}
              </div>
            ) : (
              <div className="iv-card-body">
                {refusals.slice(0, 5).map((r, i) => (
                  <div className="iv-row" key={`${r.at ?? i}-${r.symbol ?? i}`}>
                    <span>
                      <b>{r.symbol ? displaySymbol(r.symbol) : '—'}</b>
                      {r.at ? <span className="mono dim"> · {fmtTime(r.at)}</span> : null}
                    </span>
                    <span className="iv-row-v neg">{labelRiskRefusal(r.reason)}</span>
                  </div>
                ))}
              </div>
            )}
          </section>
          <section className="iv-card" id="pf-regles">
            <div className="iv-card-head">
              <div className="iv-card-tabs">
                <span className="iv-card-tab is-on">Règles et univers du compte</span>
              </div>
              <div className="iv-card-tools">Fixées dans le moteur</div>
            </div>
            {breakdown ? (
              <div className="iv-card-body">
                <div className="iv-row">
                  <span>Capital de départ</span>
                  <span className="iv-row-v">{fmtEur(breakdown.rules.initial_cash, 0)}</span>
                </div>
                <div className="iv-row">
                  <span>Risque par trade</span>
                  <span className="iv-row-v">{fmtPct(breakdown.rules.risk_pct, 2)}</span>
                </div>
                <div className="iv-row">
                  <span>Montant max. par position</span>
                  <span className="iv-row-v">{fmtPct(breakdown.rules.max_notional_pct, 0)} du capital</span>
                </div>
                <div className="iv-row">
                  <span>Positions simultanées</span>
                  <span className="iv-row-v">{breakdown.rules.max_open_positions != null ? `${breakdown.rules.max_open_positions} au plus` : "—"}</span>
                </div>
                <div className="iv-row">
                  <span>Risque ouvert total</span>
                  <span className="iv-row-v">{fmtPct(breakdown.rules.max_open_risk_pct, 1)} au plus</span>
                </div>
                <div className="iv-row">
                  <span>Perte du jour</span>
                  <span className="iv-row-v">arrêt à {fmtPct(breakdown.rules.daily_loss_limit_pct, 1)}</span>
                </div>
                <div className="iv-row">
                  <span>Ventes à découvert</span>
                  <span className="iv-row-v">{!breakdown.rules.allow_short
                      ? 'interdites (achats seulement)'
                      : breakdown.rules.short_symbols
                        ? `sur ${breakdown.rules.short_symbols.join(', ')} (jamais sur la crypto au comptant)`
                        : 'autorisées'}</span>
                </div>
                <div className="iv-row">
                  <span>Bougies du scan automatique</span>
                  <span className="iv-row-v">{(breakdown.rules.auto_timeframes ?? []).map((t) => t.toUpperCase()).join(', ') || '—'}</span>
                </div>
                <div className="iv-row">
                  <span>Objectif</span>
                  <span className="iv-row-v">{breakdown.rules.take_profit_r != null ? `${breakdown.rules.take_profit_r} R` : '—'}</span>
                </div>
                <div className="iv-row">
                  <span>Liquidité minimale</span>
                  <span className="iv-row-v">
                    {breakdown.rules.max_friction_bps != null ? `frais de marché ≤ ${breakdown.rules.max_friction_bps} pb par côté` : '—'}
                    {breakdown.rules.min_quote_volume_24h != null
                      ? ` · volume 24 h ≥ ${breakdown.rules.min_quote_volume_24h.toLocaleString('fr-FR')}`
                      : ''}
                  </span>
                </div>
                <div className="iv-row">
                  <span>Filtres structure / Fibonacci / RSI / flux / régime</span>
                  <span className="iv-row-v">{modeFr(breakdown.rules.filters_mode)}</span>
                </div>
                <div className="iv-row">
                  <span>Fenêtres de sessions</span>
                  <span className="iv-row-v">{modeFr(breakdown.rules.decision_windows_mode)}</span>
                </div>
                {enginesFr(breakdown.rules.engines).length > 0 ? (
                  <div className="iv-row pf-row-wrap">
                    <span>Décident pour ce compte</span>
                    <span className="iv-row-v">{enginesFr(breakdown.rules.engines).join(', ')}</span>
                  </div>
                ) : null}
                {arbitrationFr(breakdown.rules.arbitration) ? (
                  <p className="iv-note pf-small">
                    <b>Arbitrage :</b> {arbitrationFr(breakdown.rules.arbitration)}
                  </p>
                ) : null}
                <div className="pf-universe">
                  {universeByClass(breakdown.universe.symbols).map((g) => (
                    <div key={g.asset_class} className="pf-universe-group">
                      <div className="iv-cap">
                        {g.label} · {g.symbols.length}
                      </div>
                      <div className="pf-universe-list">
                        {g.symbols.map((sym) => (
                          <span key={sym} className="iv-tag is-muted">
                            {displaySymbol(sym)}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
                {breakdown.universe.exclusions.length > 0 ? (
                  <div className="pf-universe-group">
                    <div className="iv-cap">Exclus · {breakdown.universe.exclusions.length}</div>
                    {breakdown.universe.exclusions.map((x) => (
                      <div key={x.symbol} className="iv-row pf-row-wrap">
                        <span>{displaySymbol(x.symbol)}</span>
                        <span className="iv-row-v dim">{x.reason}</span>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="iv-empty">{loading ? 'Chargement…' : 'Règles indisponibles.'}</div>
            )}
          </section>
        </div>
      </div>

      {fiche && (
        <div className="pf-fiche-backdrop" onClick={() => setFiche(null)}>
          <div
            className="pf-fiche"
            role="dialog"
            aria-modal="true"
            aria-label={`Fiche ${displaySymbol(fiche.symbol)}`}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="pf-fiche-body">
              <div className="pf-fiche-head">
                <div>
                  <div className="iv-meta">Fiche position · paper</div>
                  <h2>
                    {displaySymbol(fiche.symbol)}{' '}
                    <span className={`iv-side ${fiche.direction === 'SHORT' ? 'is-short' : 'is-long'}`}>
                      {fiche.direction === 'SHORT' ? 'VENTE' : 'ACHAT'}
                    </span>{' '}
                    <span className="iv-cap">{String(fiche.timeframe).toUpperCase()}</span>
                  </h2>
                </div>
                <button type="button" className="iv-btn iv-btn--ghost iv-btn--sm" onClick={() => setFiche(null)} aria-label="Fermer">
                  ×
                </button>
              </div>
              <p className="iv-note">
                <DeciderMark decider={deciderOf(fiche)} />{' '}
                {fiche.source === 'rs_d1'
                  ? 'Ouverte par la règle RS-D1 (cassure Donchian 55, stop suiveur 3 ATR, sortie canal 20).'
                  : deciderOf(fiche) === 'eve'
                    ? 'Proposée par le moteur et acceptée par Ève.'
                    : deciderOf(fiche) === 'engine'
                      ? 'Ouverte par le moteur seul, sur son signal.'
                      : 'Ouverte à la main, après votre confirmation.'}{' '}
                Entrée le {new Date(fiche.entry_time).toLocaleString('fr-FR')} à {fmtPx(fiche.entry_price)}.
                {fiche.entry_decision ? ` Signal : ${fiche.entry_decision}.` : ''}{' '}
                {isActionableBuySell(fiche.entry_decision) ? <VpValidationBadge /> : null}
              </p>
              <div className="pf-fiche-grid">
                <div className="iv-row">
                  <span>Quantité</span>
                  <span className="iv-row-v">{fiche.qty != null ? fmtPx(fiche.qty) : '—'}</span>
                </div>
                <div className="iv-row">
                  <span>Notionnel</span>
                  <span className="iv-row-v">{fmtEur(fiche.notional, 2)}</span>
                </div>
                <div className="iv-row">
                  <span>Stop</span>
                  <span className="iv-row-v neg">{fmtPx(fiche.stop_price)}</span>
                </div>
                <div className="iv-row">
                  <span>Objectif</span>
                  <span className="iv-row-v ok">{fmtPx(fiche.take_profit_price)}</span>
                </div>
                <div className="iv-row">
                  <span>Prix actuel</span>
                  <span className="iv-row-v">{fmtPx(fiche.current_price)}</span>
                </div>
                <div className="iv-row">
                  <span>P&amp;L latent</span>
                  <span className={`iv-row-v ${signCls(fiche.unrealized_pnl)}`}>{fmtEur(fiche.unrealized_pnl, 2)}</span>
                </div>
                <div className="iv-row">
                  <span>Risque à l’entrée</span>
                  <span className="iv-row-v">
                    {fiche.risk_pct != null ? fmtPct(fiche.risk_pct, 2) : '—'}
                    {fiche.risk_amount != null ? ` · ${fmtEur(fiche.risk_amount, 2)}` : ''}
                  </span>
                </div>
                <div className="iv-row">
                  <span>Distance au stop</span>
                  <span className="iv-row-v">
                    {fiche.current_price != null && fiche.stop_price != null
                      ? `${fmtPx(Math.abs(fiche.current_price - fiche.stop_price))} · ${fmtPct(
                          Math.abs(fiche.current_price - fiche.stop_price) / fiche.current_price,
                          2,
                        )}`
                      : '—'}
                  </span>
                </div>
                <div className="iv-row">
                  <span>Multiple de risque (R)</span>
                  <span className="iv-row-v">
                    {(() => {
                      const r = rMultiple(fiche)
                      return r == null ? '—' : `${r > 0 ? '+' : ''}${r.toLocaleString('fr-FR', { maximumFractionDigits: 2 })} R`
                    })()}
                  </span>
                </div>
                <div className="iv-row">
                  <span>Frais d’entrée</span>
                  <span className="iv-row-v">{fmtEur(fiche.entry_fee, 2)}</span>
                </div>
                <div className="iv-row">
                  <span>Valeur de marché</span>
                  <span className="iv-row-v">
                    {fmtEur(
                      fiche.market_value ??
                        (fiche.current_price != null && fiche.qty != null ? fiche.current_price * Math.abs(fiche.qty) : null),
                      2,
                    )}
                  </span>
                </div>
              </div>
              <ObservedFilters signal={fiche.entry_signal} />
              {fiche.source !== 'rs_d1' ? (
                <MtfPanel
                  stored={storedMatrix(fiche.entry_signal)}
                  storedLabel={
                    storedMatrix(fiche.entry_signal)
                      ? `Ce que le moteur savait à l'entrée · ${fmtUtc(storedMatrix(fiche.entry_signal)?.computed_at ?? null)}`
                      : undefined
                  }
                />
              ) : null}
              <div className="ci-embed">
                <ChartIntelligencePanel
                  symbol={fiche.symbol}
                  timeframe={String(fiche.timeframe || '1h')}
                  source="api"
                  variant="brief"
                  context="position"
                  entryTime={fiche.entry_time}
                />
              </div>
              <div className="dialog-actions pf-fiche-actions">
                <button type="button" className="iv-btn iv-btn--primary" onClick={() => setFiche(null)}>
                  Fermer la fiche
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {closeTarget && (
        <PaperCloseConfirmSheet
          position={closeTarget}
          confirming={closeConfirming}
          error={closeError}
          onConfirm={() => void executeClose()}
          onCancel={() => {
            if (!closeConfirming) {
              setCloseTarget(null)
              setCloseError(null)
            }
          }}
        />
      )}
    </div>
  )
}
