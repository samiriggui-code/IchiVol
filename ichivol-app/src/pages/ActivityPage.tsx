import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  getActivityFeed,
  getActivitySummary,
  getBacktestCoverage,
  getBacktestRuns,
  getEvidenceOutcomes,
  type ActivityItem,
  type ActivitySummary,
  type BacktestCoverage,
  type BacktestRuns,
  type EvidenceOutcomes,
} from '../lib/activity'
import { getShadowStats, type ShadowStats } from '../lib/paper'
import { getScreener, type ScreenerDecisionRow } from '../lib/decisions'
import { getBacktestEvidence, type BacktestEvidenceSummary } from '../lib/backtest'
import {
  Circuit24Strip,
  EvidenceOpsCard,
  PipelineHealthCard,
} from '../components/desk/DeskRelocatedCards'
import './ActivityPage.css'

import {
  CircuitCard,
  HISTORY_FILTERS,
  LEVEL_FILTERS,
  REFRESH_MS,
  RunDetail,
  dayLabel,
  fmtAgo,
  fmtClock,
  fmtInt,
  fmtWhen,
  levelFromTone,
  qualityIssues,
  sourceFromItem,
  type HistoryFilter,
  type LevelFilter,
  type AuditRow,
  type TimelineEntry,
} from './activity/activityShared'

export function ActivityPage() {
  const [summary, setSummary] = useState<ActivitySummary | null>(null)
  const [feed, setFeed] = useState<ActivityItem[]>([])
  const [runs, setRuns] = useState<BacktestRuns | null>(null)
  const [shadow, setShadow] = useState<ShadowStats | null>(null)
  const [outcomes, setOutcomes] = useState<EvidenceOutcomes | null>(null)
  const [coverage, setCoverage] = useState<BacktestCoverage | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<HistoryFilter>('all')
  const [levelFilter, setLevelFilter] = useState<LevelFilter>('all')
  const [auditQuery, setAuditQuery] = useState('')
  const [openRun, setOpenRun] = useState<string | null>(null)
  const [screenerRows, setScreenerRows] = useState<ScreenerDecisionRow[]>([])
  const [evidenceSummary, setEvidenceSummary] = useState<BacktestEvidenceSummary | null>(null)

  const load = useCallback(async () => {
    try {
      const [s, f, r, sh, oc, cov, scr, ev] = await Promise.all([
        getActivitySummary(),
        getActivityFeed(150),
        getBacktestRuns(30),
        getShadowStats().catch(() => null),
        getEvidenceOutcomes().catch(() => null),
        getBacktestCoverage().catch(() => null),
        getScreener('1h').catch(() => null),
        getBacktestEvidence().catch(() => null),
      ])
      setSummary(s)
      setFeed(f.items)
      setRuns(r)
      setShadow(sh)
      setOutcomes(oc)
      setCoverage(cov)
      setScreenerRows(scr?.rows ?? [])
      setEvidenceSummary(ev)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Activité indisponible')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
    const id = window.setInterval(() => void load(), REFRESH_MS)
    return () => window.clearInterval(id)
  }, [load])

  const auditRows = useMemo(() => {
    const merged = new Map<string, AuditRow>()
    for (const item of feed) {
      const level = levelFromTone(item.tone)
      const key = `${item.time.slice(0, 19)}|${item.kind}|${item.symbol}|${item.detail}`
      const existing = merged.get(key)
      if (existing) {
        existing.portfolios.push(item.portfolio)
        continue
      }
      merged.set(key, {
        key,
        time: item.time,
        level,
        source: sourceFromItem(item),
        event: item.detail ? `${item.title} — ${item.detail}` : item.title,
        portfolios: [item.portfolio],
      })
    }
    return [...merged.values()].sort((a, b) => b.time.localeCompare(a.time))
  }, [feed])

  const filteredAudit = useMemo(() => {
    const q = auditQuery.trim().toLowerCase()
    return auditRows.filter((row) => {
      if (levelFilter !== 'all' && row.level !== levelFilter) return false
      if (!q) return true
      const hay = `${row.level} ${row.source} ${row.event} ${row.portfolios.join(' ')}`.toLowerCase()
      return hay.includes(q)
    })
  }, [auditRows, levelFilter, auditQuery])

  const dataQualityRows = useMemo(() => {
    return screenerRows
      .map((row) => {
        const issues = qualityIssues(row)
        const dq = row.data_quality
        const prov = row.data_provenance
        return {
          symbol: row.symbol,
          issues,
          gate: dq?.gate ?? null,
          stale: Boolean(dq?.stale),
          dataLate: Boolean(dq?.data_late),
          ok: dq?.ok !== false && issues.length === 0,
          provider: prov?.provider ?? null,
          fingerprint: prov?.dataset_fingerprint ?? null,
          nBars: prov?.n_bars ?? null,
          hasQuality: Boolean(dq),
        }
      })
      .filter((r) => r.hasQuality)
  }, [screenerRows])

  const qualityProblems = useMemo(
    () => dataQualityRows.filter((r) => !r.ok || r.issues.length > 0),
    [dataQualityRows],
  )

  const timeline = useMemo(() => {
    const entries: TimelineEntry[] = []
    if (filter !== 'backtest') {
      const merged = new Map<string, Extract<TimelineEntry, { type: 'feed' }>>()
      for (const item of feed) {
        const isPaper = item.kind === 'paper_opened' || item.kind === 'paper_closed'
        if (filter === 'paper' && !isPaper) continue
        if (filter === 'shadow' && isPaper) continue
        const key = `${item.time.slice(0, 16)}|${item.kind}|${item.symbol}|${item.detail}`
        const existing = merged.get(key)
        if (existing) existing.portfolios.push(item.portfolio)
        else merged.set(key, { type: 'feed', time: item.time, item, portfolios: [item.portfolio] })
      }
      entries.push(...merged.values())
    }
    if ((filter === 'all' || filter === 'backtest') && runs) {
      for (const run of runs.runs) entries.push({ type: 'run', time: run.ended_at, run })
    }
    entries.sort((a, b) => b.time.localeCompare(a.time))
    const groups: { day: string; entries: TimelineEntry[] }[] = []
    for (const entry of entries) {
      const day = dayLabel(entry.time)
      const last = groups[groups.length - 1]
      if (last && last.day === day) last.entries.push(entry)
      else groups.push({ day, entries: [entry] })
    }
    return groups
  }, [feed, runs, filter])

  const evidenceWired = (summary?.evidence.rows_total ?? 0) > 0
  const minTrades = runs?.min_trades_per_pair ?? 30
  const latestRun = runs?.runs[0] ?? null

  return (
    <div className="act-page">
      <header className="iv-page-header page-head market-head">
        <div className="market-head-copy">
          <p className="iv-page-eyebrow">Automatisation · Opérations</p>
          <h1>Opérations</h1>
          <p className="iv-page-question">
            L’activité du système, sans angle mort — décisions, paper, filtres, backtests.
          </p>
        </div>
        <div className="market-class-tabs">
          <Link to="/app/strategy-lab" className="link">
            Strategy Lab →
          </Link>
          <button type="button" onClick={() => void load()} disabled={loading}>
            {loading ? '…' : 'Actualiser'}
          </button>
        </div>
      </header>

      {error && (
        <div className="banner error" role="alert">
          {error}
        </div>
      )}

      <div className="desk-relocated-stack">
        <Circuit24Strip summary={summary} loading={loading} />
        <div className="desk-relocated-row">
          <PipelineHealthCard rows={screenerRows} loading={loading} />
          <EvidenceOpsCard
            evidence={evidenceSummary}
            summary={summary}
            loading={loading}
            showOpsLink={false}
          />
        </div>
      </div>

      <section className="act-circuit" aria-label="Le circuit automatique">
        <CircuitCard
          step={1}
          title="Décisions"
          what="Le moteur relit les marchés surveillés et note chaque décision."
          value={summary ? fmtInt(summary.decisions.total) : '…'}
          sub={
            summary
              ? `${fmtInt(summary.decisions.last_24h)} / 24 h · ${fmtAgo(summary.decisions.last_at)}`
              : ''
          }
          state={summary && summary.decisions.last_24h > 0 ? 'ok' : 'warn'}
        />
        <CircuitCard
          step={2}
          title="Trades papier"
          what="Ouvertures fictives quand le pipeline valide (jamais d’argent réel)."
          value={summary ? `${fmtInt(summary.paper.opened_total)} ouverts` : '…'}
          sub={
            summary
              ? `${summary.paper.open_now} en cours · ${fmtAgo(summary.paper.last_opened_at)}`
              : ''
          }
          state={summary && summary.paper.opened_total > 0 ? 'ok' : 'warn'}
        />
        <CircuitCard
          step={3}
          title="Trades refusés"
          what="Filtres structure / contexte / Fib — suivi counterfactual."
          value={summary ? `${fmtInt(summary.shadow.blocked_total)} refusés` : '…'}
          sub={summary ? `${fmtInt(summary.shadow.judged_total)} jugés` : ''}
          state={summary && summary.shadow.blocked_total > 0 ? 'ok' : 'warn'}
        />
        <CircuitCard
          step={4}
          title="Backtests"
          what="Collecte quotidienne · 5 méthodes · couverture actuelle (souvent crypto)."
          value={summary ? `${fmtInt(summary.backtest.runs_total)} runs` : '…'}
          sub={
            summary
              ? summary.backtest.last_at
                ? `dernier ${fmtAgo(summary.backtest.last_at)}`
                : 'Aucun run'
              : ''
          }
          state={summary && summary.backtest.runs_total > 0 ? 'ok' : 'warn'}
        />
        <CircuitCard
          step={5}
          title="Suivi signaux"
          what="Enregistrement signal → outcome pour prouver l’efficacité."
          value={
            !summary
              ? '…'
              : !summary.evidence.tracking_enabled
                ? 'Désactivé'
                : evidenceWired
                  ? `${fmtInt(summary.evidence.rows_total)} suivis`
                  : 'En attente'
          }
          sub={
            !summary
              ? ''
              : !summary.evidence.tracking_enabled
                ? 'suivi coupé (ENABLE_SIGNAL_TRACKING)'
                : evidenceWired
                  ? `${fmtInt(summary.evidence.measured)} mesurés · ${fmtInt(summary.evidence.complete)} terminés`
                  : 'premier signal directionnel au prochain scan'
          }
          state={!summary?.evidence.tracking_enabled ? 'off' : evidenceWired ? 'ok' : 'warn'}
        />
      </section>

      <div className="act-ops-toolbar" role="search">
        <div className="market-class-tabs act-filters" role="tablist" aria-label="Filtre niveau">
          {LEVEL_FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              role="tab"
              aria-selected={levelFilter === f.id}
              className={levelFilter === f.id ? 'is-active' : undefined}
              onClick={() => setLevelFilter(f.id)}
            >
              {f.label}
            </button>
          ))}
        </div>
        <label className="act-ops-search">
          <span className="sr-only">Rechercher dans le journal</span>
          <input
            type="search"
            placeholder="Rechercher dans le journal…"
            value={auditQuery}
            onChange={(e) => setAuditQuery(e.target.value)}
          />
        </label>
      </div>

      <div className="act-ops-grid">
        <section className="panel act-audit" aria-label="Journal d’audit">
          <header className="panel-head">
            <h2>Journal d’audit</h2>
            <span className="panel-meta">
              {loading ? '…' : `${fmtInt(filteredAudit.length)} événement${filteredAudit.length === 1 ? '' : 's'}`}
            </span>
          </header>
          {loading ? (
            <p className="muted act-empty">Chargement…</p>
          ) : error ? (
            <p className="muted act-empty">Journal indisponible.</p>
          ) : filteredAudit.length === 0 ? (
            <p className="muted act-empty">Aucun événement pour ce filtre.</p>
          ) : (
            <div className="table-wrap act-audit-table-wrap">
              <table className="act-audit-table">
                <thead>
                  <tr>
                    <th>Heure</th>
                    <th>Niveau</th>
                    <th>Source</th>
                    <th>Événement</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredAudit.map((row) => (
                    <tr key={row.key}>
                      <td className="mono muted">{fmtClock(row.time)}</td>
                      <td>
                        <span
                          className={`act-level is-${
                            row.level === 'PASSE'
                              ? 'passe'
                              : row.level === 'PRUDENCE'
                                ? 'prudence'
                                : 'refuse'
                          }`}
                        >
                          {row.level}
                        </span>
                      </td>
                      <td>{row.source}</td>
                      <td>
                        {row.event}
                        {row.portfolios.length > 1 ? (
                          <span className="muted"> · {row.portfolios.length} portes</span>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="panel act-quality" aria-label="Qualité des données">
          <header className="panel-head">
            <h2>Qualité des données</h2>
            <span className="panel-meta">screener · 1H</span>
          </header>
          {loading ? (
            <p className="muted act-empty">Chargement…</p>
          ) : dataQualityRows.length === 0 ? (
            <p className="muted act-empty">Non disponible</p>
          ) : qualityProblems.length === 0 ? (
            <p className="act-quality-ok">Aucun problème détecté</p>
          ) : (
            <ul className="act-quality-list">
              {qualityProblems.map((r) => (
                <li key={r.symbol}>
                  <div className="act-quality-row">
                    <strong className="mono">{r.symbol}</strong>
                    <span className="act-level is-prudence" aria-label="prudence">
                      PRUDENCE
                    </span>
                  </div>
                  <p className="muted act-quality-detail">
                    {r.issues.length ? r.issues.join(' · ') : 'anomalie'}
                    {r.gate ? ` · porte ${r.gate}` : ''}
                    {r.stale ? ' · stale' : ''}
                    {r.dataLate ? ' · retard' : ''}
                    {r.provider ? ` · ${r.provider}` : ''}
                    {r.nBars != null ? ` · ${fmtInt(r.nBars)} barres` : ''}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section className="panel act-trace" aria-label="Ce que la trace explique">
        <header className="panel-head">
          <h2>Ce que la trace explique</h2>
          <span className="panel-meta">décision · protection · reproductibilité</span>
        </header>
        <div className="act-trace-grid">
          <article className="act-trace-col">
            <h3 className="subhead">Décision</h3>
            {loading ? (
              <p className="muted">Chargement…</p>
            ) : outcomes && outcomes.n_used > 0 ? (
              <>
                <p className="act-trace-lead">
                  <strong className="mono">{fmtInt(outcomes.n_used)}</strong> signaux mesurés
                  {summary ? ` · ${fmtInt(summary.evidence.complete)} terminés` : ''}
                </p>
                <ul className="act-eff-list">
                  {outcomes.groups.slice(0, 3).map((g) => {
                    const h20 = g.horizons['20']
                    return (
                      <li key={g.id}>
                        <strong>{g.label}</strong>
                        {h20 && h20.n > 0 ? (
                          <>
                            {' '}
                            ·{' '}
                            <span className={(h20.mean_return ?? 0) >= 0 ? 'up' : 'down'}>
                              {(h20.mean_return ?? 0) >= 0 ? '+' : ''}
                              {((h20.mean_return ?? 0) * 100).toFixed(2)} %
                            </span>
                            <span className="muted"> à 20 bougies</span>
                          </>
                        ) : (
                          <span className="muted"> · pas encore de horizon 20</span>
                        )}
                      </li>
                    )
                  })}
                </ul>
              </>
            ) : summary && summary.evidence.rows_total > 0 ? (
              <p className="muted">
                {fmtInt(summary.evidence.rows_total)} signaux enregistrés, aucun mesuré encore.
              </p>
            ) : (
              <p className="muted">Non disponible</p>
            )}
          </article>

          <article className="act-trace-col">
            <h3 className="subhead">Protection</h3>
            {loading ? (
              <p className="muted">Chargement…</p>
            ) : shadow && shadow.n_closed > 0 ? (
              <>
                <p className="act-trace-lead">
                  Verdict filtres : <strong>{shadow.filter_verdict ?? 'inconnu'}</strong>
                  {shadow.n_closed < 5 ? ' · échantillon mince' : ''}
                </p>
                <ul className="act-eff-list">
                  {Object.entries(shadow.by_block_source)
                    .slice(0, 4)
                    .map(([source, s]) => {
                      const helped = s.mean_pnl_r < 0
                      return (
                        <li key={source}>
                          <strong>{source}</strong> · {s.n} refusés ·{' '}
                          <span className={helped ? 'up' : 'down'}>
                            {s.mean_pnl_r >= 0 ? '+' : ''}
                            {s.mean_pnl_r.toFixed(2)} R
                          </span>
                        </li>
                      )
                    })}
                </ul>
              </>
            ) : summary && summary.shadow.blocked_total > 0 ? (
              <p className="muted">
                {fmtInt(summary.shadow.blocked_total)} refusés · {fmtInt(summary.shadow.judged_total)}{' '}
                jugés — pas encore de stats fermées.
              </p>
            ) : (
              <p className="muted">Non disponible</p>
            )}
          </article>

          <article className="act-trace-col">
            <h3 className="subhead">Reproductibilité</h3>
            {loading ? (
              <p className="muted">Chargement…</p>
            ) : latestRun ? (
              <>
                <p className="act-trace-lead">
                  Dernier run : pipeline bat Ichimoku sur{' '}
                  <strong className="mono">
                    {latestRun.pipeline_vs_ichimoku.beats}/{latestRun.pipeline_vs_ichimoku.compared}
                  </strong>{' '}
                  paires
                </p>
                <p className="muted act-eff-note">
                  {fmtWhen(latestRun.ended_at)} · {latestRun.n_pairs} paires ·{' '}
                  {fmtInt(latestRun.n_rows)} rows
                  {coverage
                    ? ` · couverture ${coverage.crypto_symbols} cryptos × ${coverage.timeframes.join(' / ')}`
                    : ''}
                </p>
              </>
            ) : (
              <p className="muted">Non disponible</p>
            )}
          </article>
        </div>
      </section>

      <section className="panel act-history" aria-label="Historique">
        <header className="panel-head">
          <h2>Historique</h2>
          <div className="market-class-tabs act-filters" role="tablist" aria-label="Filtre historique">
            {HISTORY_FILTERS.map((f) => (
              <button
                key={f.id}
                type="button"
                role="tab"
                aria-selected={filter === f.id}
                className={filter === f.id ? 'is-active' : undefined}
                onClick={() => setFilter(f.id)}
              >
                {f.label}
              </button>
            ))}
          </div>
        </header>

        {!loading && timeline.length === 0 && (
          <p className="muted act-empty">Aucune activité pour ce filtre.</p>
        )}

        {timeline.map((group) => (
          <div key={group.day} className="act-day">
            <h3 className="subhead act-day-title">{group.day}</h3>
            <ul className="act-list">
              {group.entries.map((entry) => {
                if (entry.type === 'run') {
                  const key = entry.run.started_at
                  const open = openRun === key
                  const v = entry.run.pipeline_vs_ichimoku
                  return (
                    <li key={`run-${key}`} className="act-row is-run">
                      <span className="act-time mono muted">{fmtWhen(entry.run.ended_at).slice(-5)}</span>
                      <span className="act-dot is-run" aria-hidden />
                      <div className="act-body">
                        <button
                          type="button"
                          className="act-run-toggle"
                          onClick={() => setOpenRun(open ? null : key)}
                        >
                          <strong>Backtest auto</strong>
                          <span className="muted">
                            {' '}
                            · {entry.run.n_pairs} paires · {fmtInt(entry.run.n_rows)} rows · edge{' '}
                            {v.beats}/{v.compared}
                          </span>
                          <span className="act-chevron muted" aria-hidden>
                            {open ? '▾' : '▸'}
                          </span>
                        </button>
                        {open && <RunDetail run={entry.run} minTrades={minTrades} />}
                      </div>
                    </li>
                  )
                }
                const it = entry.item
                return (
                  <li
                    key={`${it.time}-${it.kind}-${it.symbol}-${it.portfolio}-${it.detail}`}
                    className="act-row"
                  >
                    <span className="act-time mono muted">{fmtWhen(it.time).slice(-5)}</span>
                    <span className={`act-dot is-${it.tone}`} aria-hidden />
                    <div className="act-body">
                      <strong>{it.title}</strong>
                      <span className="act-detail muted">{it.detail}</span>
                    </div>
                    <span className="act-portfolio muted" title={entry.portfolios.join(', ')}>
                      {entry.portfolios.length > 1
                        ? `${entry.portfolios.length} portes`
                        : it.portfolio}
                    </span>
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
      </section>
    </div>
  )
}
