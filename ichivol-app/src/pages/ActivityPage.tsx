/**
 * Opérations — poste de trading premium (primitives iv-, voir src/theme/PREMIUM.md).
 * Données = engine (manquant → « — »).
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { portfolioLabel } from '../lib/mainPortfolio'
import { DecisionPipelinePanel } from '../components/DecisionPipelinePanel'
import { SignalEvidenceCard } from '../components/SignalEvidenceCard'
import {
  getActivityFeed,
  getActivitySummary,
  type ActivityItem,
  type ActivitySummary,
  type FeedTone,
} from '../lib/activity'
import {
  getDecisionDetail,
  getScreener,
  type DecisionDetail,
  type ScreenerDecisionRow,
} from '../lib/decisions'
import { pipelineFromDecisionDetail } from '../lib/decisionPipeline'
import { displaySymbol } from '../lib/markets'
import '../components/engineEvidence.css'
import { usePaged } from '../components/table/usePaged'
import { TablePager } from '../components/table/TablePager'
import './ActivityPage.css'

type OpsFilter = 'Tous' | 'PASSE' | 'PRUDENCE' | 'REFUSÉ'
type AuditLevel = 'PASSE' | 'PRUDENCE' | 'REFUSÉ'
type AuditRow = {
  key: string
  time: string
  level: AuditLevel
  source: string
  event: string
  item: ActivityItem
}

/** Libellés lisibles des niveaux (les codes internes et le filtrage restent inchangés). */
const LEVEL_LABEL: Record<AuditLevel, string> = {
  PASSE: 'Favorable',
  PRUDENCE: 'À surveiller',
  REFUSÉ: 'Défavorable',
}
const FILTER_LABEL: Record<OpsFilter, string> = {
  Tous: 'Tous',
  PASSE: 'Favorables',
  PRUDENCE: 'À surveiller',
  REFUSÉ: 'Défavorables',
}
const LEVEL_TONE: Record<AuditLevel, string> = {
  PASSE: 'is-mint',
  PRUDENCE: 'is-amber',
  REFUSÉ: 'is-sell',
}

function LevelTag({ level }: { level: AuditLevel }) {
  return <span className={`iv-tag ${LEVEL_TONE[level]}`}>{LEVEL_LABEL[level]}</span>
}

function fmtWhen(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(+d)) return '—'
  return d.toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function fmtClock(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(+d)) return '—'
  return d.toLocaleTimeString('fr-FR', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

function levelFromTone(tone: FeedTone): AuditLevel {
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

function sourceFromItem(item: ActivityItem): string {
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

function qualityIssues(row: ScreenerDecisionRow): string[] {
  const dq = row.data_quality
  if (!dq) return []
  const out: string[] = []
  if (dq.stale) out.push('bougie périmée')
  if (dq.data_late) out.push('données en retard')
  if (dq.issue_codes?.length) out.push(...dq.issue_codes)
  if (dq.ok === false && out.length === 0) out.push(dq.gate ?? 'qualité')
  return out
}

export function ActivityPage() {
  const [opsFilter, setOpsFilter] = useState<OpsFilter>('Tous')
  const [query, setQuery] = useState('')
  const [feed, setFeed] = useState<ActivityItem[]>([])
  const [screener, setScreener] = useState<ScreenerDecisionRow[]>([])
  const [summary, setSummary] = useState<ActivitySummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<ActivityItem | null>(null)
  const [dossier, setDossier] = useState<DecisionDetail | null>(null)
  const [dossierError, setDossierError] = useState<string | null>(null)
  const [dossierLoading, setDossierLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [f, s, sum] = await Promise.all([
        getActivityFeed(80).catch(() => ({ items: [] as ActivityItem[] })),
        getScreener('1h').catch(() => ({ rows: [] as ScreenerDecisionRow[] })),
        getActivitySummary().catch(() => null),
      ])
      setFeed(f.items ?? [])
      setScreener(s.rows ?? [])
      setSummary(sum)
    } catch {
      setFeed([])
      setScreener([])
      setSummary(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const rows: AuditRow[] = useMemo(() => {
    return feed.map((item, i) => ({
      key: `${item.time}-${item.symbol}-${i}`,
      time: fmtClock(item.time),
      level: levelFromTone(item.tone),
      source: sourceFromItem(item),
      event: item.title || item.detail || '—',
      item,
    }))
  }, [feed])

  const openRow = useCallback((item: ActivityItem) => {
    setSelected(item)
    setDossier(null)
    setDossierError(null)
    if (!item.symbol || item.symbol === '?') return
    setDossierLoading(true)
    void getDecisionDetail(item.symbol, '1h', false)
      .then((d) => setDossier(d))
      .catch((err: unknown) =>
        setDossierError(err instanceof Error ? err.message : 'Décision indisponible'),
      )
      .finally(() => setDossierLoading(false))
  }, [])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return rows.filter((r) => {
      if (opsFilter !== 'Tous' && r.level !== opsFilter) return false
      if (!q) return true
      return (
        r.event.toLowerCase().includes(q) ||
        r.source.toLowerCase().includes(q) ||
        r.level.toLowerCase().includes(q)
      )
    })
  }, [rows, opsFilter, query])

  // Pagination (5 / 10 / 20 / 50) appliquée après filtre et recherche.
  const paged = usePaged(filtered, 'operations-journal-audit')

  const quality = useMemo(() => {
    const problems = screener
      .map((row) => {
        const issues = qualityIssues(row)
        return issues.length ? { symbol: row.symbol, issues } : null
      })
      .filter(Boolean) as { symbol: string; issues: string[] }[]

    const providerOk = screener.length > 0
    const firstProblem = problems[0] ?? null
    const gapCount = screener.filter((r) =>
      (r.data_quality?.issue_codes ?? []).some((c) => /gap|missing|hole/i.test(c)),
    ).length

    return {
      providerOk,
      firstProblem,
      gapCount,
      problemCount: problems.length,
    }
  }, [screener])

  const count = (level: AuditLevel) => rows.filter((r) => r.level === level).length

  return (
    <div className="ops-page">
      <div className="iv-ph">
        <div>
          <div className="iv-meta">Opérations · journal d’audit</div>
          <h1>Opérations</h1>
          <p>L’activité du système, sans angle mort.</p>
        </div>
        <div className="iv-ph-act ops-toolbar">
          <input
            id="log-search"
            className="iv-input ops-search"
            type="search"
            placeholder="Rechercher dans le journal…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <div className="iv-seg" role="group" aria-label="Filtrer le journal par niveau">
            {(['Tous', 'PASSE', 'PRUDENCE', 'REFUSÉ'] as OpsFilter[]).map((f) => (
              <button
                key={f}
                type="button"
                aria-pressed={opsFilter === f}
                className={`iv-seg-btn${opsFilter === f ? ' is-on' : ''}`}
                onClick={() => setOpsFilter(f)}
                title={
                  f === 'Tous'
                    ? 'Toutes les lignes du journal'
                    : f === 'PASSE'
                      ? 'Sorties gagnantes, et refus qui ont évité une perte'
                      : f === 'PRUDENCE'
                        ? 'Ouvertures et trades refusés, à suivre'
                        : 'Sorties perdantes, et refus qui ont coûté un gain'
                }
              >
                {FILTER_LABEL[f]}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="iv-kpis ops-kpis">
        <div className="iv-kpi">
          <div className="iv-kpi-k">Décisions moteur</div>
          <div className="iv-kpi-v">{summary ? summary.decisions.last_24h.toLocaleString('fr-FR') : '—'}</div>
          <div className="iv-kpi-s">{summary ? `sur 24 h · ${summary.decisions.total.toLocaleString('fr-FR')} au total` : '—'}</div>
        </div>
        <div className="iv-kpi">
          <div className="iv-kpi-k">Positions paper</div>
          <div className="iv-kpi-v">{summary ? summary.paper.open_now : '—'}</div>
          <div className="iv-kpi-s">
            {summary
              ? `ouverte${summary.paper.open_now === 1 ? '' : 's'} · ${summary.paper.closed_total} clôturées`
              : '—'}
          </div>
        </div>
        <div className="iv-kpi">
          <div className="iv-kpi-k">Symboles lus</div>
          <div className={`iv-kpi-v ${!loading && screener.length > 0 ? (quality.problemCount > 0 ? 'warn' : 'ok') : ''}`}>
            {loading ? '—' : screener.length}
          </div>
          <div className="iv-kpi-s">screener 1h</div>
        </div>
        <div className="iv-kpi">
          <div className="iv-kpi-k">Bougies manquantes</div>
          <div className={`iv-kpi-v ${!loading && quality.gapCount > 0 ? 'warn' : ''}`}>
            {loading ? '—' : quality.gapCount}
          </div>
          <div className="iv-kpi-s">
            {loading
              ? '—'
              : quality.firstProblem
                ? `${displaySymbol(quality.firstProblem.symbol)} · ${quality.firstProblem.issues.join(', ')}`
                : 'aucune alerte qualité'}
          </div>
        </div>
        <div className="iv-kpi">
          <div className="iv-kpi-k">Campagnes de backtest</div>
          <div className="iv-kpi-v">{summary ? summary.backtest.runs_total : '—'}</div>
          <div className="iv-kpi-s">{summary ? `dernière ${fmtWhen(summary.backtest.last_at)}` : '—'}</div>
        </div>
      </div>

      <div className="iv-grid">
        <section className="iv-card iv-s8 iv-m-s12 ops-main">
          <div className="iv-card-head">
            <div className="iv-card-tabs">
              <span className="iv-card-tab is-on">Journal d’audit</span>
            </div>
            <div className="iv-card-tools">
              {loading
                ? '—'
                : `${filtered.length} ligne${filtered.length > 1 ? 's' : ''} · ${count('PASSE')} fav. · ${count('PRUDENCE')} à surv. · ${count('REFUSÉ')} déf.`}
            </div>
          </div>
          {filtered.length === 0 ? (
            <div className="iv-empty">{loading ? 'Chargement…' : 'Aucune ligne ne correspond.'}</div>
          ) : (
            <div className="iv-card-body is-flush iv-table-wrap">
              <table className="iv-table is-compact">
                <thead>
                  <tr>
                    <th>Heure</th>
                    <th>Niveau</th>
                    <th>Source</th>
                    <th>Événement</th>
                    <th>Compte</th>
                  </tr>
                </thead>
                <tbody>
                  {paged.rows.map((r) => (
                    <tr
                      key={r.key}
                      className={`ops-click${selected === r.item ? ' is-selected' : ''}`}
                      tabIndex={0}
                      onClick={() => openRow(r.item)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          openRow(r.item)
                        }
                      }}
                    >
                      <td className="mono dim">{r.time}</td>
                      <td>
                        <LevelTag level={r.level} />
                      </td>
                      <td>{r.source}</td>
                      <td className="ops-event">
                        <span className="ops-event-t">{r.event}</span>
                        {r.item.detail ? <span className="ops-event-d"> · {r.item.detail}</span> : null}
                      </td>
                      <td className="muted">{r.item.portfolio ? portfolioLabel(r.item.portfolio) : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <TablePager paged={paged} label="lignes" />
          <div className="iv-card-foot">Touchez une ligne pour lire la décision du moteur</div>
        </section>

        <div className="iv-s4 iv-m-s12 ops-side">
          <section className="iv-card">
            <div className="iv-card-head">
              <div className="iv-card-tabs">
                <span className="iv-card-tab is-on">Qualité des données</span>
              </div>
            </div>
            <div className="iv-card-body">
              <div className="iv-row">
                <span>Binance</span>
                <span className="iv-row-v">
                  {loading ? '—' : quality.providerOk ? <span className="iv-tag is-mint">OK</span> : '—'}
                </span>
              </div>
              <div className="iv-row">
                <span>{quality.firstProblem ? displaySymbol(quality.firstProblem.symbol) : 'Symboles du screener'}</span>
                <span className="iv-row-v">
                  {quality.firstProblem ? (
                    <span className="iv-tag is-amber">{quality.firstProblem.issues[0] ?? 'À surveiller'}</span>
                  ) : loading ? (
                    '—'
                  ) : (
                    <span className="iv-tag is-mint">OK</span>
                  )}
                </span>
              </div>
              <div className="iv-row">
                <span>Symboles lus</span>
                <span className="iv-row-v">{loading ? '—' : screener.length}</span>
              </div>
              <div className="iv-row">
                <span>Bougies manquantes</span>
                <span className={`iv-row-v ${!loading && quality.gapCount > 0 ? 'warn' : ''}`}>
                  {loading
                    ? '—'
                    : quality.gapCount > 0
                      ? `${quality.gapCount} actif${quality.gapCount > 1 ? 's' : ''}`
                      : '0'}
                </span>
              </div>
              <p className="iv-note ops-small">
                {quality.problemCount > 0
                  ? `${quality.problemCount} symbole${quality.problemCount > 1 ? 's' : ''} avec une bougie périmée ou en retard.`
                  : 'Aucune alerte qualité sur le screener.'}
              </p>
            </div>
          </section>

          <section className="iv-card iv-glow">
            <div className="iv-card-head">
              <div className="iv-card-tabs">
                <span className="iv-card-tab is-on">Ce que le moteur a produit</span>
              </div>
              <div className="iv-card-tools">24 h</div>
            </div>
            <div className="iv-card-body">
              <div className="iv-row">
                <span>Décisions</span>
                <span className="iv-row-v">
                  {summary ? `${summary.decisions.last_24h} sur 24 h · ${summary.decisions.total} au total` : '—'}
                </span>
              </div>
              <div className="iv-row">
                <span>Paper</span>
                <span className="iv-row-v">
                  {summary
                    ? `${summary.paper.open_now} ouverte${summary.paper.open_now === 1 ? '' : 's'} · ${summary.paper.closed_total} clôturées`
                    : '—'}
                </span>
              </div>
              <div className="iv-row">
                <span>Trades refusés puis jugés</span>
                <span className="iv-row-v">
                  {summary ? `${summary.shadow.blocked_total} refus · ${summary.shadow.judged_total} verdicts` : '—'}
                </span>
              </div>
              <div className="iv-row">
                <span>Campagnes de backtest</span>
                <span className="iv-row-v">{summary ? String(summary.backtest.runs_total) : '—'}</span>
              </div>
              <div className="iv-row">
                <span>Preuves mesurées</span>
                <span className="iv-row-v">
                  {summary ? `${summary.evidence.measured} / ${summary.evidence.rows_total}` : '—'}
                </span>
              </div>
              {summary && summary.evidence.rows_total > 0 ? (
                <div className="iv-bar is-mint ops-bar" title="Part des preuves déjà mesurées">
                  <i style={{ width: `${Math.min(100, (summary.evidence.measured / summary.evidence.rows_total) * 100)}%` }} />
                </div>
              ) : null}
            </div>
          </section>
        </div>
      </div>

      {selected && (
        <div className="ops-fiche-backdrop" onClick={() => setSelected(null)}>
          <div
            className="ops-dossier"
            role="dialog"
            aria-modal="true"
            aria-label={`Récit ${displaySymbol(selected.symbol)}`}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="dialog-body">
              <div className="ops-dossier-head">
                <div>
                  <div className="iv-meta">Journal d’audit · {sourceFromItem(selected)}</div>
                  <h2>
                    {displaySymbol(selected.symbol)} · {selected.title}
                  </h2>
                </div>
                <button
                  type="button"
                  className="iv-btn iv-btn--ghost iv-btn--sm"
                  onClick={() => setSelected(null)}
                  aria-label="Fermer"
                >
                  ×
                </button>
              </div>
              <p className="iv-note">{selected.detail || 'Le journal n’a pas de détail pour cette ligne.'}</p>
              <div className="ops-dossier-rows">
                <div className="iv-row">
                  <span>Heure</span>
                  <span className="iv-row-v">{fmtClock(selected.time)}</span>
                </div>
                <div className="iv-row">
                  <span>Niveau</span>
                  <span className="iv-row-v">
                    <LevelTag level={levelFromTone(selected.tone)} />
                  </span>
                </div>
                <div className="iv-row">
                  <span>Portefeuille</span>
                  <span className="iv-row-v">{selected.portfolio ? portfolioLabel(selected.portfolio) : '—'}</span>
                </div>
              </div>
              {dossierLoading ? <p className="iv-note">Lecture de la décision moteur…</p> : null}
              {dossierError ? <p className="iv-empty is-error">{dossierError}</p> : null}
              {dossier ? (
                <>
                  <DecisionPipelinePanel view={pipelineFromDecisionDetail(dossier)} />
                  <SignalEvidenceCard detail={dossier} />
                </>
              ) : null}
              <div className="dialog-actions">
                <button type="button" className="iv-btn iv-btn--primary" onClick={() => setSelected(null)}>
                  Fermer
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
