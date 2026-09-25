import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  DeskCardShell,
  DeskRing,
  RING_COLORS,
  concentrationFromPositions,
  drawdownFromCurve,
} from '../components/desk/DeskRings'
import { LabsPaperCard } from '../components/desk/DeskRelocatedCards'
import {
  getPaperOverview,
  listPaperPortfolios,
  type PaperOverview,
  type PaperPortfolioRow,
} from '../lib/paper'
import { getRiskLock, type RiskLockState } from '../lib/riskLock'
import { PaperPage } from './PaperPage'
import { SynthesePage } from './SynthesePage'
import './PortfolioPage.css'
import '../components/desk/DeskRings.css'

type PortfolioTab = 'synthese' | 'compte' | 'positions' | 'risque' | 'tests'

const BASELINE = 'ICHIVOL_BASELINE_V1'

function normalizeTab(raw: string | null): PortfolioTab {
  if (raw === 'positions' || raw === 'paper') return 'positions'
  if (raw === 'compte' || raw === 'account') return 'compte'
  if (raw === 'risque' || raw === 'risk') return 'risque'
  if (raw === 'tests') return 'tests'
  return 'synthese'
}

function fmtPct(v: number | null | undefined, digits = 1, signed = false): string {
  if (v == null || !Number.isFinite(v)) return '—'
  const n = new Intl.NumberFormat('fr-FR', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
    signDisplay: signed ? 'exceptZero' : 'auto',
  }).format(v * 100)
  return `${n} %`
}

function fmtEur(v: number | null | undefined, digits = 0): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(v)
}

function fmtMoney(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 }).format(v)
}

function riskVerdict(lock: RiskLockState | null): { label: 'PASSE' | 'BLOQUÉ'; tone: 'pass' | 'block' } {
  if (lock?.entries_blocked || lock?.kill_switch_armed || lock?.daily_loss_locked) {
    return { label: 'BLOQUÉ', tone: 'block' }
  }
  return { label: 'PASSE', tone: 'pass' }
}

/**
 * T14a + T13b + UI-P2 — Portefeuille maquette : KPI / Risk Kernel / anneaux au-dessus des onglets.
 */
export function PortfolioPage() {
  const [params, setParams] = useSearchParams()
  const active = useMemo(() => normalizeTab(params.get('tab')), [params])
  const [overview, setOverview] = useState<PaperOverview | null>(null)
  const [ovError, setOvError] = useState<string | null>(null)
  const [ovLoading, setOvLoading] = useState(true)
  const [lock, setLock] = useState<RiskLockState | null>(null)
  const [labs, setLabs] = useState<PaperPortfolioRow[]>([])
  const [labsLoading, setLabsLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLabsLoading(true)
    listPaperPortfolios()
      .then((rows) => {
        if (!cancelled) setLabs(rows.filter((p) => p.is_active))
      })
      .catch(() => {
        if (!cancelled) setLabs([])
      })
      .finally(() => {
        if (!cancelled) setLabsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    setOvLoading(true)
    Promise.all([
      getPaperOverview(BASELINE)
        .then((ov) => ({ ok: true as const, ov }))
        .catch((err: unknown) => ({
          ok: false as const,
          error: err instanceof Error ? err.message : 'Overview indisponible',
        })),
      getRiskLock(BASELINE).catch(() => null),
    ]).then(([ovRes, lockRes]) => {
      if (cancelled) return
      if (ovRes.ok) {
        setOverview(ovRes.ov)
        setOvError(null)
      } else {
        setOverview(null)
        setOvError(ovRes.error)
      }
      setLock(lockRes)
      setOvLoading(false)
    })
    return () => {
      cancelled = true
    }
  }, [])

  function selectTab(next: PortfolioTab) {
    const nextParams = new URLSearchParams(params)
    if (next === 'synthese') nextParams.delete('tab')
    else nextParams.set('tab', next === 'positions' ? 'positions' : next)
    setParams(nextParams, { replace: true })
  }

  const acct = overview?.account
  const risk = overview?.risk
  const drawdown = useMemo(
    () => drawdownFromCurve(overview?.equity_curve ?? [], acct?.equity),
    [overview?.equity_curve, acct?.equity],
  )
  const investedPct =
    acct && acct.equity > 0 ? Math.min(100, Math.max(0, (acct.invested / acct.equity) * 100)) : 0
  const concentration = useMemo(
    () => concentrationFromPositions(overview?.positions ?? []),
    [overview?.positions],
  )
  const verdict = riskVerdict(lock)

  return (
    <div className="portfolio-page desk-workspace">
      <header className="iv-page-header page-head portfolio-page-header iv-animate-soft">
        <div>
          <p className="iv-page-eyebrow">Trading · Portefeuille</p>
          <h1>Portefeuille</h1>
          <p className="iv-page-question">Le capital d’abord. Le risque toujours.</p>
        </div>
      </header>

      {ovError && (
        <div className="banner error" role="alert">
          {ovError}
        </div>
      )}

      <section className="iv-metrics desk-kpis portfolio-kpis iv-animate-in" aria-label="Indicateurs portefeuille">
        <div className="iv-metric">
          <div className="iv-metric-label">Capital</div>
          <div className="iv-metric-value mono">
            {ovLoading && !acct ? '—' : acct ? fmtEur(acct.equity, 0) : '—'}
          </div>
          <small>Equity paper · EUR</small>
        </div>
        <div className="iv-metric">
          <div className="iv-metric-label">Exposition</div>
          <div className="iv-metric-value mono">{acct ? fmtEur(acct.invested, 0) : '—'}</div>
          <small>
            {acct && acct.equity > 0 ? `${fmtPct(acct.invested / acct.equity, 1)} du capital` : 'Engagé'}
          </small>
        </div>
        <div className="iv-metric">
          <div className="iv-metric-label">Disponible</div>
          <div className="iv-metric-value mono">{acct ? fmtEur(acct.cash, 0) : '—'}</div>
          <small>Cash libre</small>
        </div>
        <div className={`iv-metric${drawdown != null && drawdown < 0 ? ' is-bear' : ''}`}>
          <div className="iv-metric-label">Drawdown</div>
          <div className="iv-metric-value mono">
            {drawdown != null ? fmtPct(drawdown, 1, true) : '—'}
          </div>
          <small>Pic equity_curve → equity</small>
        </div>
      </section>

      <div className="portfolio-maquette-row">
        <DeskCardShell title="Risk Kernel" meta={risk?.kernel ?? BASELINE}>
          {ovLoading && !risk && !lock ? (
            <p className="muted">Chargement…</p>
          ) : !risk && !lock ? (
            <p className="muted">Risque indisponible.</p>
          ) : (
            <div className="portfolio-kernel">
              <div className={`portfolio-kernel-verdict is-${verdict.tone}`}>
                <span>Verdict</span>
                <strong>{verdict.label}</strong>
                <small>
                  {[
                    lock?.kill_switch_armed ? 'kill-switch armé' : null,
                    lock?.daily_loss_locked ? 'perte journalière verrouillée' : null,
                    lock?.entries_blocked && !lock.kill_switch_armed && !lock.daily_loss_locked
                      ? 'entrées bloquées'
                      : null,
                    verdict.tone === 'pass' ? 'entrées autorisées' : null,
                  ]
                    .filter(Boolean)
                    .join(' · ')}
                </small>
              </div>
              <div className="desk-risk-bars">
                {risk?.open_risk_pct != null && risk.max_open_risk_pct != null ? (
                  <div>
                    <div className="desk-risk-label">
                      <span>Risque ouvert / limite</span>
                      <span className="mono">
                        {fmtPct(risk.open_risk_pct, 1)} / {fmtPct(risk.max_open_risk_pct, 0)}
                      </span>
                    </div>
                    <div className="desk-risk-track" aria-hidden>
                      <i
                        style={{
                          width: `${Math.min(
                            100,
                            (risk.open_risk_pct / risk.max_open_risk_pct) * 100,
                          )}%`,
                        }}
                      />
                    </div>
                  </div>
                ) : null}
                {risk && risk.max_open_positions > 0 ? (
                  <div>
                    <div className="desk-risk-label">
                      <span>Positions / max</span>
                      <span className="mono">
                        {risk.open_positions} / {risk.max_open_positions}
                      </span>
                    </div>
                    <div className="desk-risk-track" aria-hidden>
                      <i
                        style={{
                          width: `${Math.min(
                            100,
                            (risk.open_positions / risk.max_open_positions) * 100,
                          )}%`,
                        }}
                      />
                    </div>
                  </div>
                ) : null}
                {!risk?.max_open_risk_pct && !(risk && risk.max_open_positions > 0) ? (
                  <p className="muted">Aucune limite risque exposée par l’engine.</p>
                ) : null}
              </div>
            </div>
          )}
        </DeskCardShell>
      </div>

      <div className="desk-allocation portfolio-allocation">
        <DeskCardShell title="Allocation du capital" meta={acct ? fmtEur(acct.equity, 0) : undefined}>
          {!acct ? (
            <p className="muted">{ovLoading ? 'Chargement…' : 'Compte indisponible.'}</p>
          ) : (
            <div className="allocation-body">
              <DeskRing
                parts={[{ pct: investedPct, color: '#548f87' }]}
                center={fmtPct(investedPct / 100, 1)}
                label="Capital engagé"
              />
              <div className="allocation-legend">
                <div className="statline">
                  <span>
                    <i className="legend-dot teal" aria-hidden /> Engagé
                  </span>
                  <b className="mono">{fmtEur(acct.invested, 0)}</b>
                </div>
                <div className="statline">
                  <span>
                    <i className="legend-dot neutral" aria-hidden /> Liquidités
                  </span>
                  <b className="mono">{fmtEur(acct.cash, 0)}</b>
                </div>
              </div>
            </div>
          )}
        </DeskCardShell>

        <DeskCardShell title="Concentration des positions">
          {!concentration.length ? (
            <p className="muted">
              {ovLoading ? 'Chargement…' : 'Aucune position valorisée pour calculer la concentration.'}
            </p>
          ) : (
            <div className="allocation-body">
              <DeskRing
                parts={concentration.slice(0, 5).map((c, i) => ({
                  pct: c.pct,
                  color: RING_COLORS[i % RING_COLORS.length],
                }))}
                center={String(concentration.length)}
                label="Positions"
              />
              <div className="allocation-legend">
                {concentration.slice(0, 5).map((c, i) => (
                  <div key={c.symbol} className="statline concentration-row">
                    <span>
                      <i
                        className="legend-dot"
                        style={{ background: RING_COLORS[i % RING_COLORS.length] }}
                        aria-hidden
                      />
                      {c.symbol}
                    </span>
                    <b className="mono">{fmtPct(c.pct / 100, 1)}</b>
                  </div>
                ))}
              </div>
            </div>
          )}
        </DeskCardShell>
      </div>

      <div className="portfolio-tabs" role="tablist" aria-label="Sections portefeuille">
        {(
          [
            ['synthese', 'Synthèse'],
            ['compte', 'Compte'],
            ['positions', 'Positions'],
            ['risque', 'Risque'],
            ['tests', 'Tests'],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={active === id}
            className={`portfolio-tab${active === id ? ' is-active' : ''}`}
            onClick={() => selectTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="desk-relocated-stack">
        <LabsPaperCard portfolios={labs} loading={labsLoading} />
      </div>

      <div className="portfolio-tab-panel" role="tabpanel">
        {active === 'synthese' && (
          <div className="portfolio-embed is-synthese">
            <SynthesePage />
          </div>
        )}
        {active === 'compte' && (
          <div className="portfolio-embed">
            <p className="muted portfolio-embed-hint">
              Vue compte paper — détail technique aussi dans{' '}
              <Link to="/app/portefeuille?tab=positions">Positions</Link>.
            </p>
            <PaperPage />
          </div>
        )}
        {active === 'positions' && (
          <div className="portfolio-embed">
            <PaperPage />
          </div>
        )}
        {active === 'risque' && (
          <div className="portfolio-embed portfolio-risk">
            <p className="muted portfolio-embed-hint">
              Détail Risk Kernel — capital, exposé, risque utilisé, derniers refus.
            </p>
            {ovError && (
              <div className="banner error" role="alert">
                {ovError}
              </div>
            )}
            {!ovError && !risk && <p className="muted">{ovLoading ? 'Chargement…' : 'Risque indisponible.'}</p>}
            {risk && (
              <>
                <dl className="portfolio-risk-grid">
                  <div>
                    <dt>Capital (equity)</dt>
                    <dd className="mono">{fmtMoney(risk.capital)}</dd>
                  </div>
                  <div>
                    <dt>Cash</dt>
                    <dd className="mono">{fmtMoney(risk.cash)}</dd>
                  </div>
                  <div>
                    <dt>Exposé</dt>
                    <dd className="mono">{fmtMoney(risk.exposed)}</dd>
                  </div>
                  <div>
                    <dt>Risque utilisé</dt>
                    <dd className="mono">
                      {fmtMoney(risk.open_risk_amount)}
                      {risk.open_risk_pct != null ? ` · ${fmtPct(risk.open_risk_pct)}` : ''}
                      {risk.max_open_risk_pct != null
                        ? ` / lim. ${fmtPct(risk.max_open_risk_pct)}`
                        : ''}
                    </dd>
                  </div>
                  <div>
                    <dt>Positions ouvertes</dt>
                    <dd className="mono">
                      {risk.open_positions} / {risk.max_open_positions}
                    </dd>
                  </div>
                </dl>
                <h2 className="portfolio-risk-h2">Derniers refus</h2>
                {risk.recent_refusals.length === 0 ? (
                  <p className="muted">Aucun refus journalisé récemment.</p>
                ) : (
                  <div className="table-wrap">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Quand</th>
                          <th>Symbole</th>
                          <th>TF</th>
                          <th>Code</th>
                        </tr>
                      </thead>
                      <tbody>
                        {risk.recent_refusals.map((r, i) => (
                          <tr key={`${r.at}-${r.symbol}-${i}`}>
                            <td className="mono muted">
                              {r.at ? new Date(r.at).toLocaleString('fr-FR') : '—'}
                            </td>
                            <td>{r.symbol ?? '—'}</td>
                            <td>{r.timeframe ?? '—'}</td>
                            <td className="mono">{(r.codes && r.codes[0]) || r.reason || '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}
          </div>
        )}
        {active === 'tests' && (
          <div className="portfolio-embed">
            <p className="muted portfolio-embed-hint">
              Tests / shadow broker — section Paper. Disponible avec T13x pour un onglet dédié.
            </p>
            <PaperPage />
          </div>
        )}
      </div>
    </div>
  )
}
