import type { PaperProgress } from '../lib/paper'
import { signedEur } from '../lib/tradeStory'

function Gauge({ label, value, max, unit }: { label: string; value: number; max: number; unit: string }) {
  const p = Math.min(100, (value / max) * 100)
  return (
    <div className="progress-gauge">
      <div className="progress-gauge-head">
        <span>{label}</span>
        <span className="mono">
          {value} / {max} {unit}
        </span>
      </div>
      <div className="progress-gauge-bar" aria-hidden>
        <span style={{ width: `${p.toFixed(1)}%` }} />
      </div>
    </div>
  )
}

const CHECK_LABELS: Record<string, string> = {
  net_positive: 'Bénéfice net positif',
  net_without_top3_positive: 'Positif même sans les 3 meilleures transactions',
  two_of_three_periods_positive: 'Positif sur 2 périodes sur 3',
  drawdown_under_15pct: 'Perte maximale sous 15 %',
}

/** Où en est le test en direct : combien de données il reste à réunir avant de pouvoir juger le système. */
export function TestProgressPanel({ progress }: { progress: PaperProgress }) {
  const ready = progress.verdict !== 'insufficient'
  return (
    <div className="progress-panel">
      <p className={`progress-verdict progress-verdict--${progress.verdict}`}>
        <strong>{progress.verdict_label}</strong>
        {!ready && progress.eta_days_to_min_trades != null && progress.eta_days_to_min_trades > 0 && (
          <span className="muted">
            {' '}
            · au rythme actuel ({progress.trades_per_day} transactions/jour), {progress.min_trades} transactions atteintes
            dans ~{Math.ceil(progress.eta_days_to_min_trades)} j
          </span>
        )}
      </p>
      <Gauge label="Transactions clôturées" value={progress.closed_trades} max={progress.min_trades} unit="" />
      <Gauge label="Durée du test" value={Math.floor(progress.days)} max={progress.min_days} unit="jours" />
      <ul className="progress-checks">
        {Object.entries(progress.checks).map(([k, ok]) => (
          <li key={k} className={ready ? (ok ? 'is-ok' : 'is-ko') : 'is-wait'}>
            <span aria-hidden>{ready ? (ok ? '✓' : '✗') : '·'}</span> {CHECK_LABELS[k] ?? k}
          </li>
        ))}
      </ul>
      <p className="muted progress-note">
        Résultat des trades clos : {signedEur(progress.net_realized_closed)} · sans les 3 meilleurs :{' '}
        {signedEur(progress.net_without_top3)} · perte maximale {progress.max_drawdown_pct} %
      </p>
      <p className="muted progress-note">{progress.rules}</p>
    </div>
  )
}
