/**
 * Portefeuille — port littéral de design-reference/ichivol-workspace `portefeuille()` + page-head.
 * Classes HTML = maquette. Données = engine (manquant → « — »).
 * Clôture paper : confirmation (PaperCloseConfirmSheet) → closePaperPosition.
 */

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import { PaperCloseConfirmSheet } from '../components/PaperCloseConfirmSheet'
import { ChartIntelligencePanel } from '../components/chart-intelligence'
import {
  concentrationFromPositions,
  drawdownFromCurve,
} from '../components/desk/deskMetrics'
import {
  closePaperPosition,
  getPaperActivity,
  getPaperOverview,
  type PaperOrderRow,
  type PaperOverview,
  type PaperOverviewPosition,
} from '../lib/paper'
import { getRiskLock, type RiskLockState } from '../lib/riskLock'
import { displaySymbol } from '../lib/markets'
import './PortfolioPage.css'

type BadgeTone = 'green' | 'amber' | 'red' | 'gray' | ''

function badge(text: string, tone: BadgeTone = ''): ReactNode {
  let inferred = tone
  if (!inferred) {
    inferred = /PASSE|ACCEPTÉ|OUVERTE|VALIDÉ/i.test(text)
      ? 'green'
      : /REFUS|BLOQU|ERREUR/i.test(text)
        ? 'red'
        : /PRUDENCE|ARMED|WATCH/i.test(text)
          ? 'amber'
          : ''
  }
  return <span className={`tag ${inferred}`.trim()}>{text}</span>
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

function ProgressRow({
  label,
  value,
  pct,
}: {
  label: string
  value: string
  pct: number
}) {
  const width = Math.max(0, Math.min(100, pct))
  return (
    <>
      <div className="risk-row">
        <span>{label}</span>
        <span className="mono">{value}</span>
      </div>
      <div className="track">
        <span style={{ width: `${width}%` }} />
      </div>
    </>
  )
}

function orderReasonFr(reason: string | null | undefined): string {
  switch (reason) {
    case 'open':
      return 'Ouverture'
    case 'manual_close':
      return 'Clôture manuelle'
    case 'partial_tp':
      return 'Prise partielle'
    case 'reinforce':
      return 'Renfort'
    case 'direction_flipped':
      return 'Sens inversé'
    case 'stop':
    case 'stop_hit':
    case 'stop_loss':
      return 'Stop touché'
    default:
      return reason && reason.length < 40 ? reason : ''
  }
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

function EquitySpark({ points }: { points: { t: string; equity: number }[] }) {
  const ys = points.map((p) => p.equity).filter((n) => Number.isFinite(n) && n > 0)
  if (ys.length < 2) return null
  const min = Math.min(...ys)
  const max = Math.max(...ys)
  const span = max - min || 1
  const w = 320
  const h = 64
  const d = ys
    .map((y, i) => {
      const x = (i / (ys.length - 1)) * w
      const yy = h - ((y - min) / span) * (h - 6) - 3
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${yy.toFixed(1)}`
    })
    .join(' ')
  return (
    <svg className="pf-equity" viewBox={`0 0 ${w} ${h}`} role="img" aria-label="Courbe de capital">
      <path d={d} fill="none" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  )
}

function refusalLabel(reason: string | undefined): string {
  switch (reason) {
    case 'max_positions':
      return 'Plafond de positions'
    case 'open_risk_cap':
      return 'Risque ouvert au plafond'
    case 'daily_loss_halt':
      return 'Perte du jour au plafond'
    case 'insufficient_cash_or_size':
      return 'Cash insuffisant'
    case 'position_already_open':
      return 'Déjà ouvert'
    case 'kill_switch':
      return 'Arrêt d’urgence'
    default:
      return reason && reason.length < 48 ? reason : 'Refusé'
  }
}

function fmtPx(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return '—'
  return n.toLocaleString('fr-FR', { maximumFractionDigits: 6 })
}

export function PortfolioPage() {
  const [searchParams] = useSearchParams()
  const [overview, setOverview] = useState<PaperOverview | null>(null)
  const [orders, setOrders] = useState<PaperOrderRow[]>([])
  const [lock, setLock] = useState<RiskLockState | null>(null)
  const [loading, setLoading] = useState(true)
  const [fiche, setFiche] = useState<PaperOverviewPosition | null>(null)
  const [closeTarget, setCloseTarget] = useState<PaperOverviewPosition | null>(null)
  const [closeConfirming, setCloseConfirming] = useState(false)
  const [closeError, setCloseError] = useState<string | null>(null)
  const closeLock = useRef(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [ov, lk, activity] = await Promise.all([
        getPaperOverview(),
        getRiskLock().catch(() => null),
        getPaperActivity('ICHIVOL_BASELINE_V1', 12).catch(() => [] as PaperOrderRow[]),
      ])
      setOverview(ov)
      setLock(lk)
      setOrders(activity)
    } catch {
      setOverview(null)
    } finally {
      setLoading(false)
    }
  }, [])

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

  return (
    <div className="pf-page">
      <div className="page-head">
        <div>
          <div className="eyebrow">04 / ICHIVOL WORKSPACE</div>
          <h1>Portefeuille</h1>
          <p className="subtitle">
            Compte paper. Les ordres sont simulés ici, aucun n’est envoyé à un courtier.
          </p>
        </div>
        <div className="actions">{badge('BROKER PAPER', 'gray')}</div>
      </div>

      <div className="metrics">
        <div className="metric">
          <div className="metric-label">
            Capital<span>↗</span>
          </div>
          <div className="metric-value">{acct ? fmtEur(acct.equity, 2) : loading ? '—' : '—'}</div>
          <small>Portefeuille paper</small>
        </div>
        <div className="metric">
          <div className="metric-label">
            Exposition<span>↗</span>
          </div>
          <div className="metric-value">{acct ? fmtEur(acct.invested, 2) : '—'}</div>
          <small>
            {investedPct != null ? `${fmtPctPoints(investedPct, 1)} du capital` : '—'}
          </small>
        </div>
        <div className="metric">
          <div className="metric-label">
            Disponible<span>↗</span>
          </div>
          <div className="metric-value">{acct ? fmtEur(acct.cash, 2) : '—'}</div>
          <small>Réserve non engagée</small>
        </div>
        <div className={`metric${dd != null && dd < 0 ? ' down' : ''}`.trim()}>
          <div className="metric-label">
            Drawdown<span>↗</span>
          </div>
          <div className="metric-value">{dd != null ? fmtPct(dd, 1, true) : '—'}</div>
          <small>Depuis le plus haut</small>
        </div>
      </div>

      <div className="grid">
        <section className="card">
          <div className="card-head">
            <h2>Risk Kernel</h2>
          </div>
          <div className="card-body">
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 20,
                padding: '10px 0 22px',
              }}
            >
              <span
                style={{
                  font: '42px Newsreader, Georgia, serif',
                  color:
                    riskPass === true
                      ? 'var(--green)'
                      : riskPass === false
                        ? 'var(--red)'
                        : 'var(--muted)',
                }}
              >
                {riskPass === true ? 'PASSE' : riskPass === false ? 'BLOQUÉ' : '—'}
              </span>
              <span style={{ fontSize: 12, color: 'var(--muted)' }}>
                Verdict risk kernel
                <br />
                {risk
                  ? `${risk.open_positions} position${risk.open_positions === 1 ? '' : 's'} sous surveillance`
                  : '—'}
              </span>
            </div>
            <ProgressRow
              label="Risque ouvert"
              value={
                risk?.open_risk_amount != null
                  ? `${fmtEur(risk.open_risk_amount, 2)}${
                      risk.open_risk_pct != null ? ` · ${fmtPct(risk.open_risk_pct, 2)}` : ''
                    }`
                  : '—'
              }
              pct={
                risk?.open_risk_pct != null && risk.max_open_risk_pct
                  ? (risk.open_risk_pct / risk.max_open_risk_pct) * 100
                  : 0
              }
            />
            <ProgressRow
              label="Risque par jour"
              value={
                risk?.open_risk_pct != null && risk.max_open_risk_pct != null
                  ? `${fmtPct(risk.open_risk_pct, 1).replace(' %', '')} / ${fmtPct(risk.max_open_risk_pct, 0)}`
                  : '—'
              }
              pct={
                risk?.open_risk_pct != null && risk.max_open_risk_pct
                  ? (risk.open_risk_pct / risk.max_open_risk_pct) * 100
                  : 0
              }
            />
            <ProgressRow
              label="Exposition globale"
              value={
                investedPct != null
                  ? `${fmtPctPoints(investedPct, 1).replace(' %', '')} / —`
                  : '—'
              }
              pct={investedPct ?? 0}
            />
            <ProgressRow
              label="Positions simultanées"
              value={
                risk ? `${risk.open_positions} / ${risk.max_open_positions}` : '—'
              }
              pct={
                risk && risk.max_open_positions > 0
                  ? (risk.open_positions / risk.max_open_positions) * 100
                  : 0
              }
            />
          </div>
        </section>

        <section className="card">
          <div className="card-head">
            <h2>Allocation du capital</h2>
            {badge('COMPTE PAPER', 'gray')}
          </div>
          <div className="card-body">
            <EquitySpark points={overview?.equity_curve ?? []} />
            <div
              className="donut"
              style={
                investedPct != null
                  ? {
                      background: `conic-gradient(#347d78 0 ${investedPct}%, #e9e6df ${investedPct}% 100%)`,
                    }
                  : undefined
              }
              data-label={investedPct != null ? fmtPctPoints(investedPct, 1) : '—'}
            />
            <div className="statline">
              <span>Capital de départ</span>
              <b>{acct ? fmtEur(acct.initial_cash, 2) : '—'}</b>
            </div>
            <div className="statline">
              <span>P&amp;L réalisé</span>
              <b>{acct ? fmtEur(acct.realized_pnl, 2) : '—'}</b>
            </div>
            <div className="statline">
              <span>P&amp;L latent</span>
              <b>{acct ? fmtEur(acct.unrealized_pnl, 2) : '—'}</b>
            </div>
            <div className="statline">
              <span>Variation du jour</span>
              <b>{acct?.day_change != null ? fmtEur(acct.day_change, 2) : '—'}</b>
            </div>
            <div className="statline">
              <span>Commissions</span>
              <b>{overview?.costs ? fmtEur(overview.costs.commissions, 2) : '—'}</b>
            </div>
            <div className="statline">
              <span>Spread et slippage</span>
              <b>{overview?.costs ? fmtEur(overview.costs.spread_slippage, 2) : '—'}</b>
            </div>
            <div className="statline">
              <span>Financement</span>
              <b>{overview?.costs ? fmtEur(overview.costs.financing, 2) : '—'}</b>
            </div>
            <div className="statline">
              <span>Trades clôturés</span>
              <b>
                {overview?.costs
                  ? `${overview.costs.closed_trades} · ${overview.costs.wins} gains / ${overview.costs.losses} pertes`
                  : '—'}
              </b>
            </div>
            {overview?.costs?.note ? (
              <p style={{ fontSize: 11, color: 'var(--muted)' }}>{overview.costs.note}</p>
            ) : null}
          </div>
        </section>
      </div>

      <section className="card">
        <div className="card-head">
          <h2>Positions ouvertes</h2>
          {badge(positionsBadge, 'gray')}
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ACTIF</th>
                <th>SENS</th>
                <th>QTÉ</th>
                <th>ENTRÉE</th>
                <th>DERNIER</th>
                <th>STOP</th>
                <th>P&amp;L</th>
                <th>ÉTAT</th>
              </tr>
            </thead>
            <tbody>
              {positions.length === 0 ? (
                <tr>
                  <td colSpan={8}>
                    <b>—</b>
                    <small>{loading ? 'Chargement…' : 'Aucune position ouverte'}</small>
                  </td>
                </tr>
              ) : (
                positions.map((p: PaperOverviewPosition) => {
                  const base = displaySymbol(p.symbol)
                  const engaged =
                    p.market_value ??
                    (p.current_price != null && p.qty != null
                      ? p.current_price * Math.abs(p.qty)
                      : p.notional ?? null)
                  const perf = p.unrealized_pct
                  const pnl = p.unrealized_pnl
                  const pnlCls =
                    pnl == null ? '' : pnl > 0 ? 'up' : pnl < 0 ? 'down' : ''
                  const strat =
                    p.timeframe != null
                      ? `Ichimoku × RVOL · ${String(p.timeframe).toUpperCase()}`
                      : '—'
                  return (
                    <tr
                      key={p.id ?? p.symbol}
                      className="clickable"
                      tabIndex={0}
                      onClick={() => setFiche(p)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          setFiche(p)
                        }
                      }}
                    >
                      <td>
                        <b>{base}</b>
                        <small>
                          {strat}
                          {engaged != null ? ` · ${fmtEur(engaged, 0)}` : ''}
                        </small>
                      </td>
                      <td>{p.direction === 'SHORT' ? 'Vente' : 'Achat'}</td>
                      <td>
                        <span className="mono">{p.qty != null ? fmtPx(p.qty) : '—'}</span>
                      </td>
                      <td>
                        <span className="mono">{fmtPx(p.entry_price)}</span>
                      </td>
                      <td>
                        <span className="mono">{fmtPx(p.current_price)}</span>
                      </td>
                      <td>
                        <span className="mono">{fmtPx(p.stop_price)}</span>
                      </td>
                      <td>
                        <span className={`mono ${pnlCls}`.trim()}>
                          {fmtEur(pnl, 2)}
                          {perf != null ? ` · ${fmtPct(perf, 2, true)}` : ''}
                        </span>
                      </td>
                      <td>
                        <div className="pf-pos-state">
                          {badge(p.mark_stale ? 'COURS PÉRIMÉ' : 'OUVERTE', p.mark_stale ? 'amber' : '')}
                          {p.id ? (
                            <button
                              type="button"
                              className="suggestion pf-close-btn"
                              onClick={(e) => {
                                e.stopPropagation()
                                setCloseError(null)
                                setCloseTarget(p)
                              }}
                            >
                              Fermer
                            </button>
                          ) : null}
                        </div>
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

      <section className="card">
        <div className="card-head">
          <h2>Carnet d’ordres</h2>
          {badge(orders.length ? `${orders.length} DERNIERS` : '—', 'gray')}
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>HEURE</th>
                <th>ACTIF</th>
                <th>SENS</th>
                <th>QTÉ</th>
                <th>PRIX EXÉCUTÉ</th>
                <th>FRAIS</th>
                <th>STATUT</th>
              </tr>
            </thead>
            <tbody>
              {orders.length === 0 ? (
                <tr>
                  <td colSpan={7}>
                    <b>—</b>
                    <small>{loading ? 'Chargement…' : 'Aucun ordre paper'}</small>
                  </td>
                </tr>
              ) : (
                orders.map((o) => (
                  <tr key={o.id}>
                    <td>
                      {Number.isNaN(Date.parse(o.time))
                        ? '—'
                        : new Date(o.time).toLocaleString('fr-FR', {
                            day: '2-digit',
                            month: '2-digit',
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                    </td>
                    <td>
                      <b>{displaySymbol(o.symbol)}</b>
                      <small>
                        {String(o.timeframe).toUpperCase()}
                        {orderReasonFr(o.reason) ? ` · ${orderReasonFr(o.reason)}` : ''}
                      </small>
                    </td>
                    <td>{o.side === 'SELL' ? 'Vente' : 'Achat'}</td>
                    <td>
                      <span className="mono">{fmtPx(o.qty)}</span>
                    </td>
                    <td>
                      <span className="mono">{fmtPx(o.filled_price)}</span>
                    </td>
                    <td>
                      <span className="mono">{fmtEur(o.fee, 2)}</span>
                    </td>
                    <td>{badge(o.status === 'FILLED' ? 'EXÉCUTÉ' : o.status, 'gray')}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {(risk?.recent_refusals?.length ?? 0) > 0 && (
        <>
          <div style={{ height: 20 }} />
          <section className="card">
            <div className="card-head">
              <h2>Ordres refusés par le risque</h2>
            </div>
            <div className="card-body">
              {risk!.recent_refusals.slice(0, 5).map((r, i) => (
                <div className="statline" key={`${r.at ?? i}-${r.symbol ?? i}`}>
                  <span>
                    {r.symbol ? displaySymbol(r.symbol) : '—'}
                    {r.at
                      ? ` · ${new Date(r.at).toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}`
                      : ''}
                  </span>
                  <b>{refusalLabel(r.reason)}</b>
                </div>
              ))}
            </div>
          </section>
        </>
      )}

      <div style={{ height: 20 }} />

      <section className="card">
        <div className="card-head">
          <h2>Concentration des positions</h2>
        </div>
        <div className="card-body">
          {concentration.length === 0 ? (
            <p style={{ fontSize: 11, color: 'var(--muted)' }}>—</p>
          ) : (
            <>
              {concentration.map((c) => (
                <ProgressRow
                  key={c.symbol}
                  label={c.symbol}
                  value={`${fmtPctPoints(c.pct, 1)} de l’exposition`}
                  pct={c.pct}
                />
              ))}
              <p style={{ fontSize: 11, color: 'var(--muted)' }}>
                {concentration.length} ligne{concentration.length > 1 ? 's' : ''} ouverte
                {concentration.length > 1 ? 's' : ''}. Le broker paper n’ajoute pas une position
                si le cash ou le plafond de risque ne suit pas.
              </p>
            </>
          )}
        </div>
      </section>

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
            <div className="dialog-head">
              <h2>
                {displaySymbol(fiche.symbol)} · {String(fiche.direction)} ·{' '}
                {String(fiche.timeframe).toUpperCase()}
              </h2>
              <button type="button" onClick={() => setFiche(null)} aria-label="Fermer">
                ×
              </button>
            </div>
            <p>
              {fiche.source === 'auto_watchlist'
                ? 'Ouverte par le screener.'
                : 'Ouverte après votre confirmation.'}{' '}
              Entrée le {new Date(fiche.entry_time).toLocaleString('fr-FR')} à{' '}
              {fmtPx(fiche.entry_price)}.
              {fiche.entry_decision ? ` Signal : ${fiche.entry_decision}.` : ''}
            </p>
            <div className="ci-embed">
              <ChartIntelligencePanel
                symbol={fiche.symbol}
                timeframe={String(fiche.timeframe || '1h')}
                source="api"
                variant="brief"
                context="position"
              />
            </div>
            <div className="statline">
              <span>Quantité</span>
              <b>{fiche.qty != null ? fmtPx(fiche.qty) : '—'}</b>
            </div>
            <div className="statline">
              <span>Notionnel</span>
              <b>{fmtEur(fiche.notional, 2)}</b>
            </div>
            <div className="statline">
              <span>Stop</span>
              <b>{fmtPx(fiche.stop_price)}</b>
            </div>
            <div className="statline">
              <span>Objectif</span>
              <b>{fmtPx(fiche.take_profit_price)}</b>
            </div>
            <div className="statline">
              <span>Prix actuel</span>
              <b>{fmtPx(fiche.current_price)}</b>
            </div>
            <div className="statline">
              <span>P&amp;L latent</span>
              <b>{fmtEur(fiche.unrealized_pnl, 2)}</b>
            </div>
            <div className="statline">
              <span>Risque à l’entrée</span>
              <b>
                {fiche.risk_pct != null ? fmtPct(fiche.risk_pct, 2) : '—'}
                {fiche.risk_amount != null ? ` · ${fmtEur(fiche.risk_amount, 2)}` : ''}
              </b>
            </div>
            <div className="statline">
              <span>Distance au stop</span>
              <b>
                {fiche.current_price != null && fiche.stop_price != null
                  ? `${fmtPx(Math.abs(fiche.current_price - fiche.stop_price))} · ${fmtPct(
                      Math.abs(fiche.current_price - fiche.stop_price) / fiche.current_price,
                      2,
                    )}`
                  : '—'}
              </b>
            </div>
            <div className="statline">
              <span>Multiple de risque (R)</span>
              <b>
                {(() => {
                  const r = rMultiple(fiche)
                  return r == null ? '—' : `${r > 0 ? '+' : ''}${r.toLocaleString('fr-FR', { maximumFractionDigits: 2 })} R`
                })()}
              </b>
            </div>
            <div className="statline">
              <span>Frais d’entrée</span>
              <b>{fmtEur(fiche.entry_fee, 2)}</b>
            </div>
            <div className="statline">
              <span>Valeur de marché</span>
              <b>
                {fmtEur(
                  fiche.market_value ??
                    (fiche.current_price != null && fiche.qty != null
                      ? fiche.current_price * Math.abs(fiche.qty)
                      : null),
                  2,
                )}
              </b>
            </div>
            <button type="button" className="primary" onClick={() => setFiche(null)}>
              Fermer la fiche
            </button>
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
