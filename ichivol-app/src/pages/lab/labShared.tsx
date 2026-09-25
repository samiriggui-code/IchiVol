import type { ExperimentName, StoredExperimentSummary } from '../../lib/backtest'
import type { EngineAssetClass } from '../../lib/universe'

export const EXPERIMENT_ORDER: ExperimentName[] = [
  'ICHIMOKU_ONLY',
  'ICHIMOKU_RVOL',
  'ICHIMOKU_RVOL_ENTRY_GATE',
  'PIPELINE',
]

export const EXPERIMENT_LABELS: Record<ExperimentName, string> = {
  ICHIMOKU_ONLY: 'Ichimoku seul',
  ICHIMOKU_RVOL: 'Ichimoku + RVOL (continu)',
  ICHIMOKU_RVOL_ENTRY_GATE: 'Ichimoku + RVOL (entrée)',
  PIPELINE: 'Pipeline (portes)',
}

export const TIMEFRAMES = ['15m', '1h', '4h', '1d']

export type LabTab = 'compare' | 'regimes' | 'experiments' | 'live' | 'research'

/** Maquette labels mapped onto existing views (content unchanged). */
export const LAB_TABS: { id: LabTab; label: string }[] = [
  { id: 'compare', label: 'Backtests' },
  { id: 'regimes', label: 'Régimes' },
  { id: 'experiments', label: 'Expériences' },
  { id: 'live', label: 'Ablations / WF' },
  { id: 'research', label: 'Research' },
]

export const IDEA_TO_PROOF_STEPS: { title: string; body: string }[] = [
  { title: 'Hypothèse', body: 'Définir ce que l’on cherche à améliorer.' },
  { title: 'Backtest', body: 'Mesurer rendement, risque et coûts.' },
  { title: 'Walk-forward', body: 'Vérifier hors échantillon.' },
  { title: 'Paper', body: 'Observer avant toute exécution réelle.' },
]

export type EquitySeries = { label: string; points: number[] }

export function asRecord(v: unknown): Record<string, unknown> | null {
  return v != null && typeof v === 'object' && !Array.isArray(v)
    ? (v as Record<string, unknown>)
    : null
}

/** Pull numeric equity path from a payload field if present (no invention). */
export function pointsFromUnknown(raw: unknown): number[] | null {
  if (!Array.isArray(raw) || raw.length < 2) return null
  const nums: number[] = []
  for (const item of raw) {
    if (typeof item === 'number' && Number.isFinite(item)) {
      nums.push(item)
      continue
    }
    if (Array.isArray(item) && typeof item[1] === 'number' && Number.isFinite(item[1])) {
      nums.push(item[1] as number)
      continue
    }
    const row = asRecord(item)
    if (!row) return null
    const v =
      typeof row.equity === 'number'
        ? row.equity
        : typeof row.value === 'number'
          ? row.value
          : typeof row.v === 'number'
            ? row.v
            : null
    if (v == null || !Number.isFinite(v)) return null
    nums.push(v)
  }
  return nums.length >= 2 ? nums : null
}

export function collectEquitySeries(payloads: unknown[]): EquitySeries[] {
  const out: EquitySeries[] = []
  const seen = new Set<string>()

  function visit(node: unknown, fallbackLabel: string, depth: number) {
    if (depth > 4 || node == null) return
    if (Array.isArray(node)) {
      const pts = pointsFromUnknown(node)
      if (pts) {
        const key = `${fallbackLabel}:${pts.length}:${pts[0]}:${pts[pts.length - 1]}`
        if (!seen.has(key)) {
          seen.add(key)
          out.push({ label: fallbackLabel, points: pts })
        }
      }
      return
    }
    const rec = asRecord(node)
    if (!rec) return
    for (const key of ['equity_curve', 'equity_series'] as const) {
      if (!(key in rec)) continue
      const pts = pointsFromUnknown(rec[key])
      if (pts) {
        const label =
          typeof rec.name === 'string'
            ? rec.name
            : typeof rec.ruleset_id === 'string'
              ? rec.ruleset_id
              : typeof rec.variant === 'string'
                ? rec.variant
                : fallbackLabel
        const id = `${label}:${pts.length}:${pts[0]}:${pts[pts.length - 1]}`
        if (!seen.has(id)) {
          seen.add(id)
          out.push({ label, points: pts })
        }
      }
    }
    if (rec.experiments && typeof rec.experiments === 'object') {
      for (const [name, exp] of Object.entries(rec.experiments as Record<string, unknown>)) {
        visit(exp, name, depth + 1)
        const er = asRecord(exp)
        if (er?.backtest) visit(er.backtest, name, depth + 1)
      }
    }
    if (Array.isArray(rec.steps)) {
      for (const step of rec.steps) {
        const sr = asRecord(step)
        visit(step, typeof sr?.label === 'string' ? sr.label : fallbackLabel, depth + 1)
      }
    }
  }

  for (const p of payloads) visit(p, 'Série', 0)
  return out
}

export function EquitySparkline({ series }: { series: EquitySeries[] }) {
  const w = 320
  const h = 96
  const pad = 6
  const colors = ['var(--bull)', 'var(--muted-foreground)', 'var(--primary)']
  return (
    <div className="bt-equity-chart" aria-hidden>
      <svg viewBox={`0 0 ${w} ${h}`} className="bt-equity-svg" role="img">
        {series.slice(0, 3).map((s, si) => {
          const min = Math.min(...s.points)
          const max = Math.max(...s.points)
          const span = max - min || 1
          const d = s.points
            .map((v, i) => {
              const x = pad + (i / (s.points.length - 1)) * (w - pad * 2)
              const y = h - pad - ((v - min) / span) * (h - pad * 2)
              return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`
            })
            .join(' ')
          return (
            <path
              key={`${s.label}-${si}`}
              d={d}
              fill="none"
              stroke={colors[si % colors.length]}
              strokeWidth={1.6}
              strokeDasharray={si === 2 ? '4 3' : undefined}
            />
          )
        })}
      </svg>
      <div className="bt-equity-legend">
        {series.slice(0, 3).map((s, si) => (
          <span key={`${s.label}-${si}`} style={{ color: colors[si % colors.length] }}>
            — {s.label}
          </span>
        ))}
      </div>
    </div>
  )
}

export const REGIME_FILTERS = ['ALL', 'GLOBAL', 'TRENDING', 'RANGING', 'HIGH_VOL', 'LOW_VOL', 'BULL', 'BEAR'] as const

export const CLASS_ORDER: EngineAssetClass[] = [
  'crypto',
  'forex',
  'metal',
  'index',
  'equity',
  'energy',
]

export function fmtPct(v: number | null, digits = 1): string {
  return v == null ? '—' : `${(v * 100).toFixed(digits)}%`
}

export function fmtNum(v: number | null, digits = 2): string {
  return v == null || !Number.isFinite(v) ? '—' : v.toFixed(digits)
}

export function toneClass(v: number | null): string {
  if (v == null) return ''
  return v >= 0 ? 'up' : 'down'
}

export function friendlyBacktestError(raw: string): string {
  const lower = raw.toLowerCase()
  if (lower.includes('credit') || lower.includes('rate limit') || lower.includes('8 api')) {
    return 'Quota Twelve Data dépassé — attends ~1 min avant un autre backtest equity.'
  }
  if (lower.includes('provider_not_wired')) {
    return 'Instrument non câblé côté moteur (pas encore de provider).'
  }
  if (lower.includes('engine_unreachable') || lower.includes('502')) {
    return 'Moteur Python injoignable — vérifie que le service tourne (ichivol-app/engine).'
  }
  return raw
}

export function fmtWhen(iso: string | null): string {
  if (!iso) return 'jamais'
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return '—'
  const ageSec = (Date.now() - t) / 1000
  if (ageSec < 3600) return `il y a ${Math.max(1, Math.floor(ageSec / 60))} min`
  if (ageSec < 86400) return `il y a ${Math.floor(ageSec / 3600)} h`
  return `il y a ${Math.floor(ageSec / 86400)} j`
}

export function metricsBasisLabel(basis: string | null | undefined): string {
  if (basis === 'net_v2') return 'net (engine v2)'
  if (basis === 'net_v1') return 'net (ruleset v1)'
  return 'brut (ancien)'
}

export function metricsBasisBucket(basis: string | null | undefined): string {
  if (basis === 'net_v2') return 'net_v2'
  if (basis === 'net_v1') return 'net_v1'
  return 'gross'
}

export function StoredMetricsTable({
  rows,
  emptyHint,
  showRegime = false,
}: {
  rows: StoredExperimentSummary[]
  emptyHint: string
  showRegime?: boolean
}) {
  if (rows.length === 0) {
    return (
      <div className="panel placeholder-page">
        <p className="muted">{emptyHint}</p>
      </div>
    )
  }
  const bases = new Set(rows.map((r) => metricsBasisBucket(r.metrics_basis)))
  const mixed = bases.size > 1
  return (
    <div className="table-wrap">
      {mixed ? (
        <p className="muted" style={{ padding: '0.5rem 1rem 0', color: 'var(--danger, #c44)' }}>
          Attention : bases différentes (brut / net_v1 / net_v2) — ne pas comparer côte à côte
          sans le dire.
        </p>
      ) : null}
      <table>
        <thead>
          <tr>
            <th>Ruleset</th>
            {showRegime && <th>Régime</th>}
            <th>Base</th>
            <th>Essais</th>
            <th>Cx</th>
            <th>Trades</th>
            <th>WR</th>
            <th>PF</th>
            <th>Expect.</th>
            <th>Sharpe</th>
            <th>DD</th>
            <th>Quand</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((e) => (
            <tr key={e.experiment_id}>
              <td className="mono" style={{ fontSize: '0.8em' }}>
                {e.ruleset_id}
                {e.hypothesis_id ? (
                  <div className="muted" style={{ fontSize: '0.85em' }}>
                    hyp:{e.hypothesis_id}
                  </div>
                ) : null}
              </td>
              {showRegime && (
                <td className="mono" style={{ fontSize: '0.8em' }}>
                  {e.market_regime ?? '—'}
                </td>
              )}
              <td className="mono" style={{ fontSize: '0.75em' }}>
                {metricsBasisLabel(e.metrics_basis)}
              </td>
              <td className="mono" title="Compteur d'essais (ligneage T10b)">
                {e.lineage_count ?? '—'}
              </td>
              <td
                className="mono"
                title={
                  e.complexity
                    ? `complexité ${e.complexity.score} (entry ${e.complexity.entry_leaves} / exit ${e.complexity.exit_leaves} / extras ${e.complexity.exit_extras}) — display-only`
                    : 'complexité display-only'
                }
              >
                {e.complexity?.score ?? '—'}
              </td>
              <td className="mono">{e.number_of_trades}</td>
              <td className="mono">{fmtPct(e.win_rate)}</td>
              <td className="mono">{fmtNum(e.profit_factor)}</td>
              <td className={`mono ${toneClass(e.expectancy)}`}>{fmtPct(e.expectancy)}</td>
              <td className="mono">{fmtNum(e.sharpe)}</td>
              <td className="mono down">{fmtPct(e.max_drawdown)}</td>
              <td className="mono" style={{ fontSize: '0.8em' }}>
                {e.created_at ? fmtWhen(e.created_at) : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

