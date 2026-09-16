import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ContextPanel } from '../components/ContextPanel'
import { labelDecision } from '../lib/decisionLabels'
import {
  getScreener,
  type DecisionLabel,
  type ScreenerDecisionRow,
} from '../lib/decisions'

const QUICK_LINKS = [
  {
    to: '/app/market',
    title: 'Marché',
    body: 'Screener live, chart Ichimoku × volume, signaux confirmés.',
  },
  {
    to: '/app/decisions',
    title: 'Décisions',
    body: 'Pipeline Direction → Participation → Structure → Location → Régime.',
  },
  {
    to: '/app/backtests',
    title: 'Backtests',
    body: 'Comparer Ichimoku seul vs Ichimoku × RVOL sur l’historique.',
  },
  {
    to: '/app/settings',
    title: 'Paramètres',
    body: 'Clés LLM, sources et préférences du cockpit.',
  },
]

const PIPELINE_STEPS = [
  { n: '1', label: 'Direction', hint: 'Ichimoku' },
  { n: '2', label: 'Participation', hint: 'RVOL' },
  { n: '3', label: 'Structure', hint: 'PA / MTF' },
  { n: '4', label: 'Location', hint: 'VP / VWAP' },
  { n: '5', label: 'Régime', hint: 'ATR' },
]

function fmtCacheAge(seconds: number): string {
  if (seconds < 5) return 'à l’instant'
  if (seconds < 60) return `il y a ${Math.floor(seconds)}s`
  return `il y a ${Math.floor(seconds / 60)}min`
}

function isBuy(d: DecisionLabel): boolean {
  return d === 'BUY' || d === 'STRONG_BUY'
}

function isSell(d: DecisionLabel): boolean {
  return d === 'SELL' || d === 'STRONG_SELL'
}

function isWatch(d: DecisionLabel): boolean {
  return d === 'WATCH' || d === 'WAIT'
}

function decisionTone(decision: DecisionLabel): 'bull' | 'bear' | 'neutral' {
  if (isBuy(decision)) return 'bull'
  if (isSell(decision)) return 'bear'
  return 'neutral'
}

function summarize(rows: ScreenerDecisionRow[]) {
  let buy = 0
  let sell = 0
  let watch = 0
  for (const r of rows) {
    if (isBuy(r.decision)) buy += 1
    else if (isSell(r.decision)) sell += 1
    else if (isWatch(r.decision)) watch += 1
  }
  const top = [...rows]
    .sort((a, b) => b.confidence - a.confidence)
    .slice(0, 5)
  return { buy, sell, watch, top, total: rows.length }
}

export function OverviewPage() {
  const [rows, setRows] = useState<ScreenerDecisionRow[]>([])
  const [cacheAge, setCacheAge] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  function load(force = false) {
    setLoading(true)
    setError(null)
    getScreener('1h', force)
      .then((res) => {
        setRows(res.rows)
        setCacheAge(res.cache_age_seconds)
      })
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : 'Erreur de chargement'
        setError(
          msg.includes('engine_unreachable') || msg.includes('502')
            ? 'Moteur Python injoignable — lance l’engine (port 8000) pour le résumé décisions.'
            : msg,
        )
        setRows([])
        setCacheAge(null)
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [])

  const stats = useMemo(() => summarize(rows), [rows])

  return (
    <div className="overview-page">
      <header className="page-head overview-head">
        <div>
          <h1>Vue d’ensemble</h1>
          <p className="muted">
            Cockpit IchiVol — structure, participation, puis risque. Pas une usine à indicateurs.
          </p>
        </div>
        <button type="button" className="ghost" onClick={() => load(true)} disabled={loading}>
          {loading ? 'Scan…' : 'Rafraîchir'}
        </button>
      </header>

      <section className="panel overview-pipeline" aria-label="Chaîne d’analyse">
        <span className="subhead">Chaîne d’analyse</span>
        <ol className="overview-pipeline-steps">
          {PIPELINE_STEPS.map((s) => (
            <li key={s.n}>
              <span className="overview-pipeline-n">{s.n}</span>
              <strong>{s.label}</strong>
              <span className="muted">{s.hint}</span>
            </li>
          ))}
        </ol>
      </section>

      {error && (
        <div className="banner error" role="alert">
          {error}
        </div>
      )}

      <section className="overview-stats" aria-label="Résumé screener">
        <div className="panel overview-stat">
          <span className="overview-stat-label muted">Paires scannées</span>
          <strong className="mono">{loading && !rows.length ? '—' : stats.total}</strong>
          <span className="overview-stat-meta muted">
            1h
            {cacheAge != null ? ` · ${fmtCacheAge(cacheAge)}` : ''}
          </span>
        </div>
        <div className="panel overview-stat overview-stat--bull">
          <span className="overview-stat-label muted">Achats</span>
          <strong className="mono">{stats.buy}</strong>
          <span className="overview-stat-meta muted">BUY / STRONG_BUY</span>
        </div>
        <div className="panel overview-stat overview-stat--bear">
          <span className="overview-stat-label muted">Ventes</span>
          <strong className="mono">{stats.sell}</strong>
          <span className="overview-stat-meta muted">SELL / STRONG_SELL</span>
        </div>
        <div className="panel overview-stat">
          <span className="overview-stat-label muted">Surveillance</span>
          <strong className="mono">{stats.watch}</strong>
          <span className="overview-stat-meta muted">WATCH / WAIT</span>
        </div>
      </section>

      <section className="panel overview-top">
        <header className="panel-head">
          <h2>Top confiance</h2>
          <Link to="/app/decisions" className="ghost">
            Voir décisions →
          </Link>
        </header>
        {stats.top.length === 0 ? (
          <p className="muted overview-empty">
            {loading ? 'Chargement du screener…' : 'Aucune ligne — vérifie le moteur ou rafraîchis.'}
          </p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Symbole</th>
                  <th>Décision</th>
                  <th>Conf.</th>
                  <th>RVOL</th>
                </tr>
              </thead>
              <tbody>
                {stats.top.map((r) => (
                  <tr key={r.symbol}>
                    <td>
                      <Link to="/app/decisions">
                        <strong>{r.symbol.replace(/USDT$/i, '')}</strong>
                      </Link>
                    </td>
                    <td>
                      <span className={`bias bias-${decisionTone(r.decision)}`}>
                        {labelDecision(r.decision)}
                      </span>
                    </td>
                    <td className="mono">{(r.confidence * 100).toFixed(0)}%</td>
                    <td className="mono">{r.rvol != null ? `${r.rvol.toFixed(2)}×` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <div className="overview-links">
        {QUICK_LINKS.map((l) => (
          <Link key={l.to} to={l.to} className="overview-link-card panel">
            <h3>{l.title}</h3>
            <p>{l.body}</p>
          </Link>
        ))}
      </div>

      <ContextPanel variant="compact" />
    </div>
  )
}
