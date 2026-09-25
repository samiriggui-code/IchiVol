/**
 * Portefeuille — port littéral de design-reference/ichivol-workspace `portefeuille()` + page-head.
 * Classes HTML = maquette. Données = engine (manquant → « — »).
 * Clôture paper : confirmation (PaperCloseConfirmSheet) → closePaperPosition.
 */

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { PaperCloseConfirmSheet } from '../components/PaperCloseConfirmSheet'
import {
  concentrationFromPositions,
  drawdownFromCurve,
} from '../components/desk/deskMetrics'
import { DATA_REFRESH_EVENT } from '../lib/actionFeedback'
import {
  closePaperPosition,
  getPaperOverview,
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

export function PortfolioPage() {
  const navigate = useNavigate()
  const [overview, setOverview] = useState<PaperOverview | null>(null)
  const [lock, setLock] = useState<RiskLockState | null>(null)
  const [loading, setLoading] = useState(true)
  const [closeTarget, setCloseTarget] = useState<PaperOverviewPosition | null>(null)
  const [closeConfirming, setCloseConfirming] = useState(false)
  const [closeError, setCloseError] = useState<string | null>(null)
  const closeLock = useRef(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [ov, lk] = await Promise.all([getPaperOverview(), getRiskLock().catch(() => null)])
      setOverview(ov)
      setLock(lk)
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
    const onRefresh = () => {
      void load()
    }
    window.addEventListener(DATA_REFRESH_EVENT, onRefresh)
    return () => window.removeEventListener(DATA_REFRESH_EVENT, onRefresh)
  }, [load])

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

  const openMarket = (symbol: string) => {
    navigate(`/app/market?symbol=${encodeURIComponent(symbol)}`)
  }

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
          <p className="subtitle">Le capital d’abord. Le risque toujours.</p>
        </div>
        <div className="actions">{badge('DONNÉES LIVE', 'gray')}</div>
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
              label="Risque par trade"
              value="—"
              pct={0}
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
            {badge('CRYPTO SPOT', 'gray')}
          </div>
          <div className="card-body">
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
              <span>Capital engagé</span>
              <b>{acct ? fmtEur(acct.invested, 2) : '—'}</b>
            </div>
            <div className="statline">
              <span>Liquidités</span>
              <b>{acct ? fmtEur(acct.cash, 2) : '—'}</b>
            </div>
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
                <th>ACTIF / STRATÉGIE</th>
                <th>ENGAGÉ</th>
                <th>PERFORMANCE</th>
                <th>P&amp;L LATENT</th>
                <th>ÉTAT</th>
              </tr>
            </thead>
            <tbody>
              {positions.length === 0 ? (
                <tr>
                  <td colSpan={5}>
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
                  const perfCls =
                    perf == null ? '' : perf > 0 ? 'up' : perf < 0 ? 'down' : ''
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
                      onClick={() => openMarket(p.symbol)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          openMarket(p.symbol)
                        }
                      }}
                    >
                      <td>
                        <b>{base}</b>
                        <small>{strat}</small>
                      </td>
                      <td>
                        <span className="mono">{fmtEur(engaged, 2)}</span>
                      </td>
                      <td>
                        <span className={`mono ${perfCls}`.trim()}>
                          {perf != null ? fmtPct(perf, 2, true) : '—'}
                        </span>
                      </td>
                      <td>
                        <span className={`mono ${pnlCls}`.trim()}>{fmtEur(pnl, 2)}</span>
                      </td>
                      <td>
                        <div className="pf-pos-state">
                          {badge(p.mark_stale ? 'MARK STALE' : 'OUVERTE')}
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
                {concentration.length} actif{concentration.length > 1 ? 's' : ''} crypto : surveiller
                leur corrélation avant d’ajouter une position.
              </p>
            </>
          )}
        </div>
      </section>

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
