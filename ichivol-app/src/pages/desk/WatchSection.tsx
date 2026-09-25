import { Link } from 'react-router-dom'
import { VerdictBadge } from '../../components/VerdictBadge'
import type { ScreenerDecisionRow } from '../../lib/decisions'
import type { PaperOverview, PaperOverviewPosition } from '../../lib/paper'
import type { RiskLockState } from '../../lib/riskLock'
import { CardShell } from './CardShell'
import { fmtEur, fmtPct } from './deskFormat'

export function WatchSection({
  loading,
  watchList,
  freshnessIssues,
  ovError,
  overview,
  acct,
  risk,
  lock,
}: {
  loading: boolean
  watchList: ScreenerDecisionRow[]
  freshnessIssues: string[]
  ovError: string | null
  overview: PaperOverview | null
  acct: PaperOverview['account'] | undefined
  risk: PaperOverview['risk'] | undefined
  lock: RiskLockState | null
}) {
  return (
    <div className="desk-grid-2">
      <CardShell
        title="À surveiller"
        footer={
          <Link to="/app/opportunites" className="link">
            Toutes les opportunités ↗
          </Link>
        }
      >
        {loading && !watchList.length ? (
          <p className="muted">Chargement…</p>
        ) : !watchList.length ? (
          <p className="muted">Aucune opportunité actionnable (BUY/SELL).</p>
        ) : (
          <ul className="desk-watch-list">
            {watchList.map((r) => (
              <li key={r.symbol}>
                <Link to={`/app/opportunites?symbol=${encodeURIComponent(r.symbol)}`}>
                  <strong>{r.symbol.replace(/USDT$/i, '')}</strong>
                  <VerdictBadge decision={r.decision} pipeline={r.pipeline} hideDiagnostic />
                  <span className="mono muted">{fmtPct(r.confidence, 0, false)}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </CardShell>

      {freshnessIssues.length > 0 ? (
        <div className="banner desk-freshness" role="status">
          <strong>Fraîcheur données</strong>
          <span>
            {' '}
            {freshnessIssues.slice(0, 6).join(', ')}
            {freshnessIssues.length > 6 ? ` (+${freshnessIssues.length - 6})` : ''} — données
            stale / tardives ou mark position périmé.
          </span>
          <Link to="/app/operations" className="link">
            Voir Opérations ↗
          </Link>
        </div>
      ) : null}

      <CardShell
        title="Positions ouvertes"
        meta={acct ? `${acct.open_positions} ouvertes` : undefined}
        footer={
          <Link to="/app/portefeuille?tab=positions" className="link">
            Portefeuille ↗
          </Link>
        }
      >
        {ovError ? (
          <p className="muted">{ovError}</p>
        ) : !(overview?.positions.length) ? (
          <p className="muted">Aucune position ouverte.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Actif</th>
                  <th>Engagé</th>
                  <th>P&amp;L latent</th>
                  <th>État</th>
                </tr>
              </thead>
              <tbody>
                {(overview?.positions ?? []).slice(0, 8).map((p: PaperOverviewPosition) => (
                  <tr key={p.id ?? p.symbol}>
                    <td>
                      <b>{p.symbol.replace(/USDT$/i, '')}</b>
                      <small className="muted"> {p.direction}</small>
                    </td>
                    <td className="mono">
                      {fmtEur(
                        p.market_value ??
                          (p.current_price != null && p.qty != null
                            ? p.current_price * Math.abs(p.qty)
                            : null),
                        0,
                      )}
                    </td>
                    <td
                      className={`mono ${
                        (p.unrealized_pnl ?? 0) > 0
                          ? 'up'
                          : (p.unrealized_pnl ?? 0) < 0
                            ? 'down'
                            : ''
                      }`}
                    >
                      {fmtEur(p.unrealized_pnl, 0)}
                    </td>
                    <td>{p.mark_stale ? 'Mark stale' : 'Ouverte'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardShell>

      <CardShell title="Votre budget de risque">
        {!risk ? (
          <p className="muted">{ovError ?? (loading ? 'Chargement…' : 'Risque indisponible.')}</p>
        ) : (
          <div className="desk-risk-bars">
            <div>
              <div className="desk-risk-label">
                <span>Exposition / limite</span>
                <span className="mono">
                  {risk.open_risk_pct != null ? fmtPct(risk.open_risk_pct, 1, false) : '—'}
                  {risk.max_open_risk_pct != null
                    ? ` / ${fmtPct(risk.max_open_risk_pct, 0, false)}`
                    : ''}
                </span>
              </div>
              <div className="desk-risk-track" aria-hidden>
                <i
                  style={{
                    width: `${Math.min(
                      100,
                      risk.max_open_risk_pct && risk.open_risk_pct != null
                        ? (risk.open_risk_pct / risk.max_open_risk_pct) * 100
                        : 0,
                    )}%`,
                  }}
                />
              </div>
            </div>
            <div>
              <div className="desk-risk-label">
                <span>Slots positions</span>
                <span className="mono">
                  {risk.open_positions} / {risk.max_open_positions}
                </span>
              </div>
              <div className="desk-risk-track" aria-hidden>
                <i
                  style={{
                    width: `${Math.min(
                      100,
                      risk.max_open_positions
                        ? (risk.open_positions / risk.max_open_positions) * 100
                        : 0,
                    )}%`,
                  }}
                />
              </div>
            </div>
            <p className="desk-note">
              Perte journalière :{' '}
              <strong>{lock?.daily_loss_locked ? 'verrouillée' : 'ouverte'}</strong>
              {lock?.kill_switch_armed ? ' · kill-switch armé' : ''}
            </p>
          </div>
        )}
      </CardShell>
    </div>
  )
}
