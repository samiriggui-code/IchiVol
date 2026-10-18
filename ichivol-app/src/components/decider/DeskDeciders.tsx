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

/** Contenu de la carte « Moteur vs Ève » du Desk. */
export function DeskDeciderSummary() {
  const { positions, autonomy } = useDeciderData()
  const scores = useMemo(() => scoreByDecider(positions ?? []), [positions])
  return (
    <div className="card-body ddv">
      <p className="ddv-mode">
        {autonomy == null
          ? 'Le moteur propose, Ève accepte ou refuse, le Risk Kernel a le dernier mot.'
          : autonomy
            ? 'Ève décide en ce moment : chaque proposition du moteur passe par elle avant d’être exécutée.'
            : 'L’autonomie d’Ève est coupée : le moteur trade seul en ce moment.'}
      </p>
      <div className="ddv-grid">
        {DECIDERS.map((d) => {
          const s = scores[d]
          return (
            <div key={d} className={`ddv-tile is-${d}`}>
              <DeciderBadge decider={d} />
              <b className={`mono ${s.net > 0 ? 'up' : s.net < 0 ? 'down' : ''}`.trim()}>
                {positions == null ? '…' : s.trades > 0 ? signedEur(s.net) : '—'}
              </b>
              <small>
                {s.trades > 0
                  ? `${s.trades} trade${s.trades > 1 ? 's' : ''} clôturé${s.trades > 1 ? 's' : ''} · ${fmtPct(s.winRate, 0, false)} gagnés`
                  : 'aucun trade clôturé'}
                {s.open > 0 ? ` · ${s.open} en cours` : ''}
              </small>
            </div>
          )
        })}
      </div>
      <Link className="link" to="/app/agents">
        Comparer en détail →
      </Link>
    </div>
  )
}

/** Contenu de la carte « Derniers jugements d'Ève » du Desk. */
export function DeskEveLatest() {
  const { decisions, autonomy, portfolios } = useDeciderData()
  const labels = useMemo(
    () => Object.fromEntries(portfolios.map((p) => [p.code, portfolioLabel(p.code, p.label)])),
    [portfolios],
  )
  const rows = useMemo(
    () =>
      (decisions ?? [])
        .flatMap((d) => d.engine_proposals.map((p, i) => ({ key: `${d.id}-${i}`, d, p, v: proposalVerdict(p) })))
        .slice(0, 5),
    [decisions],
  )
  return (
    <div className="card-body ddv">
      {rows.length === 0 ? (
        <p className="ddv-mode">
          {decisions == null
            ? 'Chargement…'
            : autonomy
              ? 'Aucune proposition du moteur jugée pour l’instant.'
              : 'Autonomie d’Ève coupée : pas de proposition à juger.'}
        </p>
      ) : (
        <ul className="ddv-list">
          {rows.map(({ key, d, p, v }) => (
            <li key={key}>
              <span>
                <b>{d.symbol}</b>
                <small>{labels[p.portfolio_code] ?? p.portfolio_code}</small>
              </span>
              <span className="ddv-flow">
                {engineProposalFr(p)} → <b>{eveActionFr(p.eve_action)}</b>
              </span>
              <span className={`ddv-verdict is-${v}`}>{VERDICT_SHORT[v]}</span>
            </li>
          ))}
        </ul>
      )}
      <Link className="link" to="/app/agents">
        Toutes les décisions →
      </Link>
    </div>
  )
}
