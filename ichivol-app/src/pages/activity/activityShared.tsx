import {
  EXPERIMENT_LABELS,
  type ActivityItem,
  type BacktestRun,
  type FeedTone,
} from '../../lib/activity'
import type { ScreenerDecisionRow } from '../../lib/decisions'

export type HistoryFilter = 'all' | 'paper' | 'shadow' | 'backtest'
export type LevelFilter = 'all' | 'PASSE' | 'PRUDENCE' | 'REFUSÉ'
export type AuditLevel = 'PASSE' | 'PRUDENCE' | 'REFUSÉ'

export const HISTORY_FILTERS: { id: HistoryFilter; label: string }[] = [
  { id: 'all', label: 'Tout' },
  { id: 'paper', label: 'Trades papier' },
  { id: 'shadow', label: 'Filtres' },
  { id: 'backtest', label: 'Backtests' },
]

export const LEVEL_FILTERS: { id: LevelFilter; label: string }[] = [
  { id: 'all', label: 'Tous' },
  { id: 'PASSE', label: 'PASSE' },
  { id: 'PRUDENCE', label: 'PRUDENCE' },
  { id: 'REFUSÉ', label: 'REFUSÉ' },
]

export const REFRESH_MS = 60_000

export type TimelineEntry =
  | { type: 'feed'; time: string; item: ActivityItem; portfolios: string[] }
  | { type: 'run'; time: string; run: BacktestRun }

export type AuditRow = {
  key: string
  time: string
  level: AuditLevel
  source: string
  event: string
  portfolios: string[]
}

export function fmtWhen(iso: string | null): string {
  if (!iso) return 'jamais'
  return new Date(iso).toLocaleString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function fmtClock(iso: string): string {
  return new Date(iso).toLocaleTimeString('fr-FR', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

export function fmtAgo(iso: string | null): string {
  if (!iso) return 'jamais'
  const min = Math.round((Date.now() - new Date(iso).getTime()) / 60_000)
  if (min < 1) return "à l'instant"
  if (min < 60) return `il y a ${min} min`
  if (min < 48 * 60) return `il y a ${Math.round(min / 60)} h`
  return `il y a ${Math.round(min / 1440)} j`
}

export function dayLabel(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' })
}

export function fmtInt(n: number): string {
  return n.toLocaleString('fr-FR')
}

export function fmtNumber(n: number | null, digits = 2): string {
  return n == null ? '—' : n.toFixed(digits)
}

/** Map feed tone → niveau maquette PASSE / PRUDENCE / REFUSÉ. */
export function levelFromTone(tone: FeedTone): AuditLevel {
  switch (tone) {
    case 'good':
      return 'PASSE'
    case 'blocked':
      return 'PRUDENCE'
    case 'bad':
      return 'REFUSÉ'
    case 'neutral':
      return 'PRUDENCE'
    default: {
      const _exhaustive: never = tone
      return _exhaustive
    }
  }
}

export function sourceFromItem(item: ActivityItem): string {
  switch (item.kind) {
    case 'paper_opened':
    case 'paper_closed':
      return 'Position'
    case 'shadow_blocked':
    case 'shadow_closed':
      return 'Filtres'
    default: {
      const _exhaustive: never = item.kind
      return _exhaustive
    }
  }
}

export function CircuitCard(props: {
  step: number
  title: string
  what: string
  value: string
  sub: string
  state: 'ok' | 'warn' | 'off'
}) {
  return (
    <article className={`panel overview-stat act-step is-${props.state}`}>
      <div className="act-step-top">
        <span className="overview-stat-label muted">{props.title}</span>
        <span className="act-step-num muted">{props.step}</span>
      </div>
      <strong className="mono act-step-value">{props.value}</strong>
      <span className="overview-stat-meta muted">{props.sub}</span>
      <p className="act-step-what muted">{props.what}</p>
    </article>
  )
}

export function RunDetail({ run, minTrades }: { run: BacktestRun; minTrades: number }) {
  const names = Object.keys(run.experiments)
  return (
    <div className="table-wrap act-run-table-wrap">
      <table>
        <thead>
          <tr>
            <th>Méthode</th>
            <th>Trades / paire</th>
            <th>Réussite</th>
            <th>PF médiane</th>
            <th>Sharpe</th>
          </tr>
        </thead>
        <tbody>
          {names.map((name) => {
            const e = run.experiments[name]
            return (
              <tr key={name}>
                <td>{EXPERIMENT_LABELS[name] ?? name}</td>
                <td className="mono">
                  {e.trades_mean.toFixed(1)}
                  {e.small_sample && (
                    <span
                      className="act-badge is-warn"
                      title={`Moins de ${minTrades} trades par paire : trop peu pour conclure`}
                    >
                      faible
                    </span>
                  )}
                </td>
                <td className="mono">
                  {e.win_rate_mean == null ? '—' : `${(e.win_rate_mean * 100).toFixed(0)} %`}
                </td>
                <td className="mono">{fmtNumber(e.profit_factor_median)}</td>
                <td className="mono">{fmtNumber(e.sharpe_mean)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export function qualityIssues(row: ScreenerDecisionRow): string[] {
  const dq = row.data_quality
  if (!dq) return []
  const issues: string[] = []
  if (dq.stale) issues.push('périmé')
  if (dq.data_late) issues.push('retard')
  if (dq.issue_codes?.length) issues.push(...dq.issue_codes)
  if (dq.ok === false && issues.length === 0) issues.push(dq.gate ?? 'qualité')
  if (dq.gate && /fail|block|reject|warn/i.test(dq.gate) && !issues.includes(dq.gate)) {
    issues.push(dq.gate)
  }
  return issues
}
