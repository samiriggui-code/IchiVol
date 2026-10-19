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
import { FuturesCryptoPanel } from '../components/FuturesCryptoPanel'
import { FUTURES_CRYPTO_LABEL } from '../lib/futuresCrypto'
import { fmtUtc, storedMatrix } from '../lib/mtf'
import {
  concentrationFromPositions,
  drawdownFromCurve,
} from '../components/desk/deskMetrics'
import {
  closePaperPosition,
  getPaperActivity,
  getPaperOverview,
  listPaperPortfolios,
  listPaperPositions,
  type PaperOrderRow,
  type PaperPortfolioRow,
  type PaperOverview,
  type PaperOverviewPosition,
} from '../lib/paper'
import { labelPaperOrderReason, labelRiskRefusal } from '../lib/paperLabels'
import { VpValidationBadge } from '../components/VpValidationBadge'
import { isActionableBuySell } from '../lib/vpValidationCopy'
import { getRiskLock, type RiskLockState } from '../lib/riskLock'
import { displaySymbol } from '../lib/markets'
import {
  ALL_BOOKS_CODE,
  combineLocks,
  combineOverviews,
  listActiveBooks,
  loadAllActivity,
  loadAllBooks,
  type Book,
  type BookOrder,
  type BookPosition,
} from '../lib/allBooks'
import {
  BASELINE_PORTFOLIO_CODE as BASELINE_CODE,
  FUTURES_CRYPTO_CODE,
  RS_D1_CODE,
  RS_D1_LABEL,
  SESSIONS_CODE,
  SESSIONS_LABEL,
  isRsPortfolio,
  manualActionsAllowed,
  portfolioFromParam,
  portfolioLabel,
} from '../lib/rsPortfolio'
import { bookColors } from '../components/desk/equityTrajectory'
import { DECIDER_EXPLAIN, DECIDER_LABEL, deciderOf, type Decider } from '../lib/decider'
import { usePaged } from '../components/table/usePaged'
import { TablePager } from '../components/table/TablePager'
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

/** Rendement depuis le départ (capital actuel / capital de départ − 1), pour classer les portefeuilles. */
function bookReturn(b: Book): number {
  const a = b.overview.account
  return a && a.initial_cash > 0 ? a.equity / a.initial_cash - 1 : -Infinity
}

/** Un portefeuille par ligne dans la vue « Tous » : ses chiffres à lui, et un clic ouvre son détail. */
function BooksTable({
  books,
  portfolios,
  colors,
  loading,
  onOpen,
}: {
  books: Book[]
  portfolios: PaperPortfolioRow[]
  colors: Record<string, string>
  loading: boolean
  onOpen: (code: string) => void
}) {
  const sorted = useMemo(() => [...books].sort((x, y) => bookReturn(y) - bookReturn(x)), [books])
  const paged = usePaged(sorted, 'pf-par-portefeuille')
  return (
    <section className="iv-card pf-books">
      <div className="iv-card-head">
        <div className="iv-card-tabs">
          <span className="iv-card-tab is-on">Par portefeuille</span>
        </div>
        <div className="iv-card-tools">Du meilleur au moins bon</div>
      </div>
      {books.length === 0 ? (
        <div className="iv-empty">{loading ? 'Chargement…' : 'Aucun portefeuille paper actif.'}</div>
      ) : (
        <div className="iv-card-body is-flush iv-table-wrap">
          <table className="iv-table is-compact">
            <thead>
              <tr>
                <th>Portefeuille</th>
                <th className="n">Valeur</th>
                <th className="n">Depuis départ</th>
                <th className="n">Jour</th>
                <th>Entrées</th>
                <th className="n">Réalisé</th>
                <th className="n">Latent</th>
                <th className="n">Positions</th>
                <th className="n">Trades clôturés</th>
                <th className="n">Réussite</th>
                <th className="n">Gain moy. / perte moy.</th>
                <th className="n">Frais</th>
                <th className="n">Engagé</th>
                <th className="n">Drawdown</th>
              </tr>
            </thead>
            <tbody>
              {paged.rows
                .map((b) => {
                  const a = b.overview.account
                  const r = b.overview.risk
                  const row = portfolios.find((p) => p.code === b.code)
                  const blocked = Boolean(row?.kill_switch_armed || row?.daily_loss_locked)
                  const pnl = a ? a.equity - a.initial_cash : null
                  const pnlPct = a && a.initial_cash > 0 && pnl != null ? pnl / a.initial_cash : null
                  const dd = drawdownFromCurve(b.overview.equity_curve ?? [], a?.equity)
                  const open = r?.open_positions ?? a?.open_positions ?? 0
                  const c = b.overview.costs
                  const winRate = c && c.closed_trades > 0 ? c.wins / c.closed_trades : null
                  return (
                    <tr
                      key={b.code}
                      className="pf-click"
                      tabIndex={0}
                      title={`Voir le détail de ${portfolioLabel(b.code, b.label)}`}
                      onClick={() => onOpen(b.code)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          onOpen(b.code)
                        }
                      }}
                    >
                      <td>
                        <span className="pf-book-name">
                          <i className="pf-swatch" style={{ background: colors[b.code] }} aria-hidden="true" />
                          {portfolioLabel(b.code, b.label)}
                        </span>
                      </td>
                      <td className="n">{fmtEur(a?.equity, 2).replace(' €', '')}</td>
                      <td className={`n ${signCls(pnl)}`}>{fmtPct(pnlPct, 2, true)}</td>
                      <td className={`n ${signCls(a?.day_change)}`}>{fmtSigned(a?.day_change, 2)}</td>
                      <td>{blocked ? <span className="neg">Bloquées</span> : <span className="ok">Ouvertes</span>}</td>
                      <td className={`n ${signCls(a?.realized_pnl)}`}>{fmtSigned(a?.realized_pnl, 2)}</td>
                      <td className={`n ${signCls(a?.unrealized_pnl)}`}>{fmtSigned(a?.unrealized_pnl, 2)}</td>
                      <td className="n">{r ? `${open} / ${r.max_open_positions}` : String(open)}</td>
                      <td className="n">{c ? `${c.closed_trades} · ${c.wins} / ${c.losses}` : '—'}</td>
                      <td className="n">{winRate != null ? fmtPct(winRate, 0) : '—'}</td>
                      <td className="n">
                        {c && c.wins > 0 ? fmtEur(c.sum_wins / c.wins, 2) : '—'} /{' '}
                        {c && c.losses > 0 ? fmtEur(c.sum_losses / c.losses, 2) : '—'}
                      </td>
                      <td className="n">{c ? fmtEur(c.total_costs, 2) : '—'}</td>
                      <td className="n">{fmtEur(a?.invested, 2)}</td>
                      <td className={`n ${dd != null && dd < 0 ? 'neg' : ''}`}>{dd != null ? fmtPct(dd, 1, true) : '—'}</td>
                    </tr>
                  )
                })}
            </tbody>
          </table>
        </div>
      )}
      {paged.pageCount > 1 || paged.total > 10 ? <TablePager paged={paged} label="portefeuilles" /> : null}
      <div className="iv-card-foot">Touchez un portefeuille pour ouvrir son détail</div>
    </section>
  )
}

export function PortfolioPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const pfParam = searchParams.get('pf')
  const tabParam = searchParams.get('tab')

  // `?tab=positions|risque|ordres` (notifications, Desk, anciennes routes) : on amène à la carte correspondante.
  useEffect(() => {
    if (!tabParam) return
    const id = { positions: 'pf-positions', risque: 'pf-risque', ordres: 'pf-ordres' }[tabParam]
    if (!id) return
    const t = window.setTimeout(() => document.getElementById(id)?.scrollIntoView({ block: 'start', behavior: 'smooth' }), 150)
    return () => window.clearTimeout(t)
  }, [tabParam])
  // Sans `?pf=` : tous les portefeuilles ensemble ; `?pf=CODE` : le détail d'un seul.
  const showAll = !pfParam || pfParam === ALL_BOOKS_CODE
  const code = showAll ? ALL_BOOKS_CODE : portfolioFromParam(pfParam)
  const isRs = isRsPortfolio(code)
  const isSessions = code === SESSIONS_CODE
  const isFutures = code === FUTURES_CRYPTO_CODE
  const bookOf = (row: { book_code?: string }) => row.book_code ?? code
  const [portfolios, setPortfolios] = useState<PaperPortfolioRow[]>([])
  const [books, setBooks] = useState<Book[]>([])
  const [overview, setOverview] = useState<PaperOverview | null>(null)
  const [orders, setOrders] = useState<Array<PaperOrderRow & { book_code?: string; book_label?: string }>>([])
  const [lock, setLock] = useState<RiskLockState | null>(null)
  /** Qui a décidé chaque lot (moteur seul, Ève, manuel), pour étiqueter aussi les ordres. */
  const [deciderByPosition, setDeciderByPosition] = useState<Record<string, Decider>>({})
  const [loading, setLoading] = useState(true)
  const [fiche, setFiche] = useState<PaperOverviewPosition | null>(null)
  const [closeTarget, setCloseTarget] = useState<PaperOverviewPosition | null>(null)
  const [closeConfirming, setCloseConfirming] = useState(false)
  const [closeError, setCloseError] = useState<string | null>(null)
  const closeLock = useRef(false)
  const [chartTab, setChartTab] = useState<'courbe' | 'allocation' | 'concentration'>('courbe')

  const load = useCallback(async () => {
    setLoading(true)
    void listPaperPositions()
      .then((all) => setDeciderByPosition(Object.fromEntries(all.map((p) => [p.id, deciderOf(p)]))))
      .catch(() => undefined)
    if (showAll) {
      try {
        const rows = await listActiveBooks()
        const all = await loadAllBooks(rows)
        const activity: BookOrder[] = await loadAllActivity(all, 12)
        setPortfolios(rows)
        setBooks(all)
        setOverview(combineOverviews(all))
        setLock(combineLocks(rows))
        setOrders(activity)
      } catch {
        setOverview(null)
        setBooks([])
      } finally {
        setLoading(false)
      }
      return
    }
    try {
      const [ov, lk, activity, pfs] = await Promise.all([
        getPaperOverview(code),
        getRiskLock(code).catch(() => null),
        getPaperActivity(code, 12).catch(() => [] as PaperOrderRow[]),
        listPaperPortfolios().catch(() => [] as PaperPortfolioRow[]),
      ])
      setOverview(ov)
      setLock(lk)
      setOrders(activity)
      setPortfolios(pfs)
    } catch {
      setOverview(null)
    } finally {
      setLoading(false)
    }
  }, [code, showAll])

  const knownLabels: Record<string, { label: string; title?: string }> = {
    [BASELINE_CODE]: { label: 'IchiVol' },
    [SESSIONS_CODE]: { label: 'Sessions', title: SESSIONS_LABEL },
    [FUTURES_CRYPTO_CODE]: { label: 'Futures & Crypto', title: FUTURES_CRYPTO_LABEL },
    [RS_D1_CODE]: { label: 'RS-D1', title: RS_D1_LABEL },
  }
  const allTab = { code: ALL_BOOKS_CODE, label: 'Tous', title: 'Tous les portefeuilles additionnés' as string | undefined }
  const tabs = [allTab, ...(() => {
    const fromApi = portfolios
      .filter((p) => p.is_active !== false)
      .map((p) => {
        const known = knownLabels[p.code]
        return {
          code: p.code,
          label: known?.label ?? p.label ?? p.code,
          title: known?.title,
        }
      })
    if (fromApi.length > 0) {
      // Toujours inclure le livre courant s’il manque dans la liste API.
      if (!showAll && !fromApi.some((t) => t.code === code)) {
        const known = knownLabels[code]
        fromApi.unshift({
          code,
          label: known?.label ?? code,
          title: known?.title,
        })
      }
      return fromApi
    }
    return [
      { code: BASELINE_CODE, label: 'IchiVol', title: undefined as string | undefined },
      { code: SESSIONS_CODE, label: 'Sessions', title: SESSIONS_LABEL },
      { code: FUTURES_CRYPTO_CODE, label: 'Futures & Crypto', title: FUTURES_CRYPTO_LABEL },
      { code: RS_D1_CODE, label: 'RS-D1', title: RS_D1_LABEL },
    ]
  })()]
  const selectPortfolio = (next: string) => {
    const params = new URLSearchParams(searchParams)
    if (next === ALL_BOOKS_CODE) params.delete('pf')
    else params.set('pf', next)
    params.delete('symbol')
    setFiche(null)
    setSearchParams(params)
  }

  useEffect(() => {
    void load()
  }, [load])

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

  const colors = bookColors(tabs.filter((t) => t.code !== ALL_BOOKS_CODE).map((t) => t.code))
  const currentLabel = tabs.find((t) => t.code === code)?.label ?? portfolioLabel(code)
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
  const refusals = useMemo(() => risk?.recent_refusals ?? [], [risk?.recent_refusals])

  // Pagination (5 / 10 / 20 / 50) : toutes les lignes restent accessibles, page par page.
  const pagedConcentration = usePaged(concentration, 'pf-concentration')
  const pagedPositions = usePaged(positions, 'pf-positions')
  const pagedOrders = usePaged(orders, 'pf-ordres')
  const pagedRefusals = usePaged(refusals, 'pf-refus')

  return (
    <div className="pf-page">
      <div className="iv-ph">
        <div>
          <div className="iv-meta">Portefeuille · paper · ordres simulés, aucun envoyé à l’extérieur</div>
          <h1>Portefeuille</h1>
          <p>
            {showAll
              ? `Les ${books.length || ''} portefeuilles paper additionnés : capital, positions et ordres de chacun, avec le nom du portefeuille sur chaque ligne. Touche un portefeuille pour voir son détail, ou le Desk pour la répartition et la concentration de l’ensemble. Aucun ordre n’est envoyé à un courtier.`.replace('Les  ', 'Les ')
              : isRs
              ? `${RS_D1_LABEL}. Portefeuille séparé, piloté uniquement par la règle RS-D1 (Donchian 4h) : aucun ordre manuel.`
              : isSessions
                ? 'Mêmes règles qu’IchiVol, mais le signal n’ouvre et ne ferme qu’aux ouvertures et clôtures de Tokyo, Londres et New York. Stop et objectif restent surveillés en continu.'
                : isFutures
                  ? 'Portefeuille paper dédié à trois marchés : Dow Jones (YM), or (MGC) et bitcoin. Mêmes règles qu’IchiVol, avec un plafond de risque commun aux trois. Aucun ordre n’est envoyé à un courtier.'
                  : 'Portefeuille paper. Les ordres sont simulés ici, aucun n’est envoyé à un courtier.'}
          </p>
        </div>
        <div className="iv-ph-act">
          {riskPass === true
            ? tag('Ouvert aux entrées', 'mint')
            : riskPass === false
              ? tag(showAll ? 'Entrées bloquées en partie' : 'Entrées bloquées', 'sell')
              : null}
          <span className="iv-chip">
            Risk Kernel ·{' '}
            <b className={riskPass === true ? 'ok' : riskPass === false ? 'neg' : 'dim'}>
              {riskPass === true ? 'PASSE' : riskPass === false ? 'BLOQUÉ' : '—'}
            </b>
          </span>
          {tag(
            showAll ? 'Tous · paper' : isRs ? 'RS-D1 · paper' : isSessions ? 'Sessions · paper' : isFutures ? 'Futures & Crypto · paper' : 'Paper',
            'amber',
          )}
        </div>
      </div>

      {tabs.length > 1 ? (
        <div className="iv-card pf-switch">
          <div className="iv-card-head">
            <div className="iv-card-tabs" role="tablist" aria-label="Portefeuille paper">
              {tabs.map((t) => (
                <button
                  key={t.code}
                  type="button"
                  role="tab"
                  aria-selected={code === t.code}
                  className={`iv-card-tab${code === t.code ? ' is-on' : ''}`}
                  onClick={() => selectPortfolio(t.code)}
                  title={t.title}
                >
                  {t.code === ALL_BOOKS_CODE ? (
                    <>
                      {t.label}
                      <span className="pf-tab-count">{books.length || ''}</span>
                    </>
                  ) : (
                    <>
                      <i className="pf-swatch" style={{ background: colors[t.code] }} aria-hidden="true" />
                      {t.label}
                    </>
                  )}
                </button>
              ))}
            </div>
          </div>
        </div>
      ) : null}

      <div className="iv-kpis pf-kpis">
        <div className="iv-kpi">
          <div className="iv-kpi-k">Capital de départ</div>
          <div className="iv-kpi-v">
            <KpiEur n={acct?.initial_cash} />
          </div>
          <div className="iv-kpi-s">{showAll ? `${books.length} portefeuilles` : 'Portefeuille paper'}</div>
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
          <div className={`iv-kpi-v ${dd != null && dd < 0 ? 'neg' : ''}`}>{dd != null ? fmtPct(dd, 1, true) : '—'}</div>
          <div className="iv-kpi-s">depuis le plus haut</div>
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

      {isFutures ? (
        <div className="pf-section">
          <FuturesCryptoPanel overview={overview} onChanged={() => void load()} />
        </div>
      ) : null}

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
            <div className="iv-card-tools">{showAll ? 'Tous les portefeuilles' : currentLabel}</div>
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
                {pagedConcentration.rows.map((c) => (
                  <Meter key={c.symbol} label={c.symbol} value={`${fmtPctPoints(c.pct, 1)} de l’exposition`} pct={c.pct} />
                ))}
                <TablePager paged={pagedConcentration} label="actifs" />
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
                    ? showAll
                      ? 'Au moins un portefeuille a ses entrées bloquées.'
                      : 'Entrées bloquées (arrêt d’urgence ou perte journalière).'
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
              {lock && !showAll ? (
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
              {showAll && lock && 'blocked' in lock ? (
                <div className="iv-row pf-row-wrap">
                  <span>
                    {(lock as ReturnType<typeof combineLocks>).blocked.length === 0
                      ? `Entrées ouvertes sur les ${(lock as ReturnType<typeof combineLocks>).book_count} portefeuilles.`
                      : `Entrées bloquées sur : ${(lock as ReturnType<typeof combineLocks>).blocked
                          .map((b) => `${b.label} (${b.kill && b.daily ? 'arrêt d’urgence + perte du jour' : b.kill ? 'arrêt d’urgence' : 'perte du jour'})`)
                          .join(', ')}.`}
                  </span>
                </div>
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
                    <th>Portefeuille</th>
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
                  {pagedPositions.rows.map((p: PaperOverviewPosition & Partial<BookPosition>) => {
                    const book = bookOf(p)
                    const pnl = p.unrealized_pnl
                    const perf = p.unrealized_pct
                    const r = rMultiple(p)
                    const dist = stopDistance(p)
                    const engaged =
                      p.market_value ??
                      (p.current_price != null && p.qty != null ? p.current_price * Math.abs(p.qty) : p.notional ?? null)
                    const strat =
                      p.timeframe != null
                        ? `${isRsPortfolio(book) ? 'RS-D1 Donchian' : 'Ichimoku × RVOL'} · ${String(p.timeframe).toUpperCase()}${engaged != null ? ` · ${fmtEur(engaged, 0)} engagés` : ''}`
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
                        <td>{showAll && p.book_label ? p.book_label : portfolioLabel(book, currentLabel)}</td>
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
                          {p.id && manualActionsAllowed(book) ? (
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
          <TablePager paged={pagedPositions} label="positions" />
          <div className="iv-card-foot">
            Stop et objectif surveillés en continu · touchez une ligne pour sa fiche
          </div>
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
                    <th>Portefeuille</th>
                    <th>Décideur</th>
                    <th className="n">Qté</th>
                    <th className="n">Prix exécuté</th>
                    <th className="n">Frais</th>
                    <th>Statut</th>
                  </tr>
                </thead>
                <tbody>
                  {pagedOrders.rows.map((o) => {
                    const reason = orderReasonFr(o.reason)
                    const filled = o.status === 'FILLED'
                    return (
                      <tr key={`${o.book_code ?? code}-${o.id}`}>
                        <td className="mono dim">{fmtTime(o.time)}</td>
                        <td className="sym">
                          {displaySymbol(o.symbol)}
                          <small>{String(o.timeframe).toUpperCase()}</small>
                        </td>
                        <td className={o.side === 'SELL' ? 'neg' : 'pos'}>{o.side === 'SELL' ? 'Vente' : 'Achat'}</td>
                        <td>{showAll && o.book_label ? o.book_label : currentLabel}</td>
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
          <TablePager paged={pagedOrders} label="ordres" />
        </section>

        <div className="iv-s5 iv-m-s12 pf-stack">
          {showAll ? (
            <BooksTable books={books} portfolios={portfolios} colors={colors} loading={loading} onOpen={selectPortfolio} />
          ) : null}
          <section className="iv-card">
            <div className="iv-card-head">
              <div className="iv-card-tabs">
                <span className="iv-card-tab is-on">Ordres refusés par le risque</span>
              </div>
              <div className="iv-card-tools">{refusals.length ? `${refusals.length} derniers` : ''}</div>
            </div>
            {refusals.length === 0 ? (
              <div className="iv-empty">
                {risk
                  ? 'Aucun refus récent. Les refus (ex. vente à découvert interdite) apparaissent ici quand le journal en a.'
                  : '—'}
              </div>
            ) : (
              <div className="iv-card-body">
                {pagedRefusals.rows.map((r, i) => (
                  <div className="iv-row" key={`${r.at ?? pagedRefusals.start + i}-${r.symbol ?? pagedRefusals.start + i}`}>
                    <span>
                      <b>{r.symbol ? displaySymbol(r.symbol) : '—'}</b>
                      {r.at ? <span className="mono dim"> · {fmtTime(r.at)}</span> : null}
                    </span>
                    <span className="iv-row-v neg">{labelRiskRefusal(r.reason)}</span>
                  </div>
                ))}
              </div>
            )}
            <TablePager paged={pagedRefusals} label="refus" />
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
