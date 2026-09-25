import { Link } from 'react-router-dom'
import type { ActivityItem } from '../../lib/activity'
import type { ScreenerDecisionRow } from '../../lib/decisions'
import {
  formatCountdown,
} from '../../lib/marketSessions'
import type { PaperOverview } from '../../lib/paper'
import type { RiskLockState } from '../../lib/riskLock'
import { CardShell } from './CardShell'
import { fmtClock, fmtDec } from './deskFormat'

function toneClass(tone: ActivityItem['tone']): string {
  switch (tone) {
    case 'good':
      return 'is-good'
    case 'bad':
      return 'is-bad'
    case 'blocked':
      return 'is-blocked'
    case 'neutral':
      return 'is-neutral'
    default: {
      const _exhaustive: never = tone
      return _exhaustive
    }
  }
}

export function EventsSection({
  tape,
  tapeError,
  nextClose,
  now,
  btcRow,
  loading,
  engineOk,
  risk,
  lock,
}: {
  tape: ActivityItem[]
  tapeError: string | null
  nextClose: Date
  now: Date
  btcRow: ScreenerDecisionRow | undefined
  loading: boolean
  engineOk: boolean | null
  risk: PaperOverview['risk'] | undefined
  lock: RiskLockState | null
}) {
  return (
    <div className="desk-grid-2">
      <CardShell
        title="Derniers événements"
        footer={
          <Link to="/app/operations" className="link">
            Historique ↗
          </Link>
        }
      >
        {tapeError ? (
          <p className="muted">{tapeError}</p>
        ) : !tape.length ? (
          <p className="muted">Aucun événement récent.</p>
        ) : (
          <ul className="ov-tape-list">
            {tape.map((it) => (
              <li key={`${it.time}-${it.kind}-${it.symbol}-${it.portfolio}-${it.detail}`}>
                <span className={`ov-tape-dot ${toneClass(it.tone)}`} aria-hidden />
                <span className="ov-tape-time mono muted">{fmtClock(it.time)}</span>
                <div className="ov-tape-body">
                  <strong>{it.title}</strong>
                  <span className="muted">{it.detail}</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardShell>

      <CardShell title="Le prochain contrôle">
        <dl className="desk-climate-stats">
          <div>
            <dt>Clôture bougie 1H</dt>
            <dd className="mono">
              {nextClose.toLocaleTimeString(undefined, {
                hour: '2-digit',
                minute: '2-digit',
              })}{' '}
              <small className="muted">({formatCountdown(nextClose, now)})</small>
            </dd>
          </div>
          <div>
            <dt>RVOL BTC</dt>
            <dd className="mono">
              {btcRow?.rvol != null ? `${fmtDec(btcRow.rvol, 2)}×` : '—'}
            </dd>
          </div>
        </dl>
        {!btcRow && !loading ? (
          <p className="muted">BTCUSDT absent du screener.</p>
        ) : null}
      </CardShell>

      <CardShell title="État du système">
        <ul className="desk-system-list">
          <li>
            <span>Moteur</span>
            <strong className={engineOk ? 'up' : 'down'}>
              {engineOk == null ? '…' : engineOk ? 'OK' : 'Hors ligne'}
            </strong>
          </li>
          <li>
            <span>Risk Kernel</span>
            <strong>{risk?.kernel ?? '—'}</strong>
          </li>
          <li>
            <span>Kill-switch</span>
            <strong>{lock?.kill_switch_armed ? 'Armé' : 'Désarmé'}</strong>
          </li>
          <li>
            <span>Mode</span>
            <strong>PAPER</strong>
          </li>
          <li>
            <span>Exécution réelle</span>
            <strong>Désactivée</strong>
          </li>
        </ul>
      </CardShell>
    </div>
  )
}
