/**
 * Desk : le résumé « Moteur vs Ève » (bilan par décideur) et les derniers jugements d'Ève.
 * Le détail complet est sur la page Ève (/app/agents).
 */

import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { DECIDERS, scoreByDecider } from '../../lib/decider'
import {
  engineProposalFr,
  eveActionFr,
  getEveDecisions,
  proposalVerdict,
  type EveDecision,
  type ProposalVerdict,
} from '../../lib/eveDecisions'
import { listPaperPortfolios, listPaperPositions, type PaperPortfolioRow, type PaperPosition } from '../../lib/paper'
import { portfolioLabel } from '../../lib/rsPortfolio'
import { fmtEur, fmtPct } from '../../pages/desk/deskFormat'
import { DeciderBadge } from './DeciderBadge'
import { usePaged } from '../table/usePaged'
import { TablePager } from '../table/TablePager'
import './DeskDeciders.css'

const REFRESH_MS = 60_000

const VERDICT_SHORT: Record<ProposalVerdict, string> = {
  executed: 'Exécutée',
  engine_over_eve: 'Moteur contre Ève',
  blocked_by_audit: 'Bloquée par l’audit',
  refused_by_eve: 'Refusée',
  blocked_after: 'Bloquée',
  pending: 'En attente',
}

function signedEur(v: number): string {
  return `${v > 0 ? '+' : v < 0 ? '−' : ''}${fmtEur(Math.abs(v), 2)}`
}

function useDeciderData() {
  const [positions, setPositions] = useState<PaperPosition[] | null>(null)
  const [decisions, setDecisions] = useState<EveDecision[] | null>(null)
  const [autonomy, setAutonomy] = useState<boolean | null>(null)
  const [portfolios, setPortfolios] = useState<PaperPortfolioRow[]>([])

  useEffect(() => {
    let alive = true
    const load = () => {
      void listPaperPositions()
        .then((p) => alive && setPositions(p))
        .catch(() => alive && setPositions([]))
      void getEveDecisions(40)
        .then((d) => {
          if (!alive) return
          setDecisions(d.results)
          setAutonomy(d.autonomy_enabled)
        })
        .catch(() => alive && setDecisions([]))
      void listPaperPortfolios()
        .then((p) => alive && setPortfolios(p))
        .catch(() => undefined)
    }
    load()
    const id = window.setInterval(load, REFRESH_MS)
    return () => {
      alive = false
      window.clearInterval(id)
    }
  }, [])

  return { positions, decisions, autonomy, portfolios }
}

function fmtTime(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', hour12: false })
}

const VERDICT_TONE: Record<ProposalVerdict, string> = {
  executed: 'is-mint',
  engine_over_eve: 'is-amber',
  blocked_by_audit: 'is-muted',
  refused_by_eve: 'is-cyan',
  blocked_after: 'is-amber',
  pending: 'is-muted',
}

/** Carte « Moteur vs Ève » du Desk : bilan des trades clôturés par décideur. */
export function DeskDeciderSummary({ className = '' }: { className?: string }) {
  const { positions, autonomy } = useDeciderData()
  const scores = useMemo(() => scoreByDecider(positions ?? []), [positions])
  const vs = scores.engine_over_eve
  const openTotal = DECIDERS.reduce((n, d) => n + scores[d].open, 0)
  return (
    <section className={`iv-card iv-glow ddv ${className}`.trim()}>
      <div className="iv-card-head">
        <div className="iv-card-tabs">
          <h2 className="iv-card-tab is-on ddv-title">Moteur vs Ève</h2>
        </div>
        <div className="iv-card-tools">Trades clôturés</div>
      </div>
      <div className="iv-card-body">
        <p className="iv-note ddv-mode">
          {autonomy == null ? (
            <>
              Le moteur propose, <span className="iv-kw">Ève accepte ou refuse</span>, le Risk Kernel a le dernier mot.
            </>
          ) : autonomy ? (
            <>
              <span className="iv-kw">Ève décide en ce moment</span> : chaque proposition du moteur passe par elle avant
              d’être exécutée.
            </>
          ) : (
            'L’autonomie d’Ève est coupée : le moteur trade seul en ce moment.'
          )}
        </p>
        <div className="iv-table-wrap">
          <table className="iv-table is-compact">
            <thead>
              <tr>
                <th>Décideur</th>
                <th className="n">Trades</th>
                <th className="n">Réussite</th>
                <th className="n">Net</th>
              </tr>
            </thead>
            <tbody>
              {DECIDERS.map((d) => {
                const s = scores[d]
                return (
                  <tr key={d}>
                    <td>
                      <DeciderBadge decider={d} />
                    </td>
                    <td className="n">{positions == null ? '…' : s.trades}</td>
                    <td className="n">{s.trades > 0 ? fmtPct(s.winRate, 1, false) : '—'}</td>
                    <td className={`n ${s.net > 0 ? 'pos' : s.net < 0 ? 'neg' : ''}`.trim()}>
                      {positions == null ? '…' : s.trades > 0 ? signedEur(s.net) : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        {vs.trades > 0 ? (
          <p className="iv-note ddv-vs">
            ◆ Quand Ève refuse et que le moteur trade quand même : {vs.losses} perte{vs.losses > 1 ? 's' : ''} sur{' '}
            {vs.trades}.
          </p>
        ) : null}
      </div>
      <div className="iv-card-foot">
        <span>
          Net de frais{openTotal > 0 ? ` · ${openTotal} en cours` : ''}
        </span>
        <Link to="/app/agents">Comparer en détail →</Link>
      </div>
    </section>
  )
}

/** Carte « Derniers jugements d'Ève » du Desk. */
export function DeskEveLatest({ className = '' }: { className?: string }) {
  const { decisions, autonomy, portfolios } = useDeciderData()
  const labels = useMemo(
    () => Object.fromEntries(portfolios.map((p) => [p.code, portfolioLabel(p.code, p.label)])),
    [portfolios],
  )
  const rows = useMemo(
    () =>
      (decisions ?? [])
        .flatMap((d) => d.engine_proposals.map((p, i) => ({ key: `${d.id}-${i}`, d, p, v: proposalVerdict(p) }))),
    [decisions],
  )
  const paged = usePaged(rows, 'desk-jugements-eve')
  const accepted = rows.filter((r) => r.p.eve_accepts).length
  return (
    <section className={`iv-card ddv ${className}`.trim()}>
      <div className="iv-card-head">
        <div className="iv-card-tabs">
          <h2 className="iv-card-tab is-on ddv-title">Derniers jugements d’Ève</h2>
        </div>
        <div className="iv-card-tools">
          {autonomy == null ? '—' : autonomy ? <span className="ok">Autonomie active</span> : 'Autonomie coupée'}
        </div>
      </div>
      <div className="iv-card-body ddv-judg">
        {rows.length === 0 ? (
          <p className="iv-empty">
            {decisions == null
              ? 'Chargement…'
              : autonomy
                ? 'Aucune proposition du moteur jugée pour l’instant.'
                : 'Autonomie d’Ève coupée : pas de proposition à juger.'}
          </p>
        ) : (
          <ul className="ddv-list">
            {paged.rows.map(({ key, d, p, v }) => (
              <li key={key}>
                <span className="ddv-time">{fmtTime(d.created_at)}</span>
                <div className="ddv-main">
                  <div className="ddv-line">
                    <b>{d.symbol}</b>
                    <small>{labels[p.portfolio_code] ?? p.portfolio_code}</small>
                    <span className={`iv-tag ${VERDICT_TONE[v]}`}>{VERDICT_SHORT[v]}</span>
                  </div>
                  <div className="ddv-flow">
                    Moteur : {engineProposalFr(p)} · Ève :{' '}
                    <b className={p.eve_accepts ? 'ok' : 'warn'}>{eveActionFr(p.eve_action)}</b>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
      <TablePager paged={paged} label="propositions" />
      <div className="iv-card-foot">
        <span>
          {rows.length} proposition{rows.length > 1 ? 's' : ''} · {accepted} acceptée{accepted > 1 ? 's' : ''} ·{' '}
          {rows.length - accepted} refusée{rows.length - accepted > 1 ? 's' : ''}
        </span>
        <Link to="/app/agents">Page Ève →</Link>
      </div>
    </section>
  )
}
