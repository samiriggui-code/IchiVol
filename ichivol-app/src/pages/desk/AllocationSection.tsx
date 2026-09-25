import { Link } from 'react-router-dom'
import {
  DeskRing,
  RING_COLORS,
} from '../../components/desk/DeskRings'
import type { PaperOverview } from '../../lib/paper'
import { CardShell } from './CardShell'
import { fmtEur, fmtPct, fmtPctPoints } from './deskFormat'

export function AllocationSection({
  loading,
  ovError,
  acct,
  investedPct,
  concentration,
}: {
  loading: boolean
  ovError: string | null
  acct: PaperOverview['account'] | undefined
  investedPct: number
  concentration: { symbol: string; pct: number }[]
}) {
  return (
    <div className="desk-allocation">
      <CardShell
        title="Répartition du capital"
        meta={acct ? fmtEur(acct.equity, 0) : undefined}
        footer={
          <Link to="/app/portefeuille" className="link">
            Voir l’allocation ↗
          </Link>
        }
      >
        {!acct ? (
          <p className="muted">{loading ? 'Chargement…' : ovError ?? 'Compte indisponible.'}</p>
        ) : (
          <div className="allocation-body">
            <DeskRing
              parts={[{ pct: investedPct, color: '#548f87' }]}
              center={fmtPctPoints(investedPct, 1, false)}
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
                  <i className="legend-dot neutral" aria-hidden /> Disponible
                </span>
                <b className="mono">{fmtEur(acct.cash, 0)}</b>
              </div>
              <p className="desk-note">
                {acct.equity > 0
                  ? `${fmtPct(acct.cash / acct.equity, 1, false)} du capital reste disponible.`
                  : null}
              </p>
            </div>
          </div>
        )}
      </CardShell>

      <CardShell
        title="Concentration des positions"
        footer={
          <Link to="/app/portefeuille?tab=positions" className="link">
            Surveiller la concentration ↗
          </Link>
        }
      >
        {!concentration.length ? (
          <p className="muted">
            {loading ? 'Chargement…' : 'Aucune position valorisée pour calculer la concentration.'}
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
                  <b className="mono">{fmtPctPoints(c.pct, 1, false)}</b>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardShell>
    </div>
  )
}
