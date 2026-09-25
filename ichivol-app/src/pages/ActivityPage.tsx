/**
 * Opérations — port littéral de design-reference/ichivol-workspace `operations()` + page-head.
 * Classes HTML = maquette. Données = engine (manquant → « — »).
 */

import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
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
import './ActivityPage.css'

type OpsFilter = 'Tous' | 'PASSE' | 'PRUDENCE' | 'REFUSÉ'
type AuditLevel = 'PASSE' | 'PRUDENCE' | 'REFUSÉ'
type BadgeTone = 'green' | 'amber' | 'red' | 'gray' | ''

type AuditRow = {
  key: string
  time: string
  level: AuditLevel
  source: string
  event: string
  item: ActivityItem
}

function badge(text: string, tone: BadgeTone = ''): ReactNode {
  let inferred = tone
  if (!inferred) {
    inferred = /PASSE|ACCEPTÉ|OUVERTE|VALIDÉ/i.test(text)
      ? 'green'
      : /REFUS|BLOQU|ERREUR/i.test(text)
        ? 'red'
        : /PRUDENCE|ARMED|WATCH|TRIGGERED/i.test(text)
          ? 'amber'
          : ''
  }
  return <span className={`tag ${inferred}`.trim()}>{text}</span>
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

  return (
    <div className="ops-page">
      <div className="page-head">
        <div>
          <div className="eyebrow">10 / ICHIVOL WORKSPACE</div>
          <h1>Opérations</h1>
          <p className="subtitle">L’activité du système, sans angle mort.</p>
        </div>
        <div className="actions">{badge('JOURNAL PAPER', 'amber')}</div>
      </div>

      <div className="toolbar">
        <div className="segmented">
          {(['Tous', 'PASSE', 'PRUDENCE', 'REFUSÉ'] as OpsFilter[]).map((f) => (
            <button
              key={f}
              type="button"
              className={opsFilter === f ? 'active' : ''}
              onClick={() => setOpsFilter(f)}
            >
              {f}
            </button>
          ))}
        </div>
        <input
          id="log-search"
          type="search"
          placeholder="Rechercher dans le journal…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      <div className="grid">
        <section className="card">
          <div className="card-head">
            <h2>Journal d’audit</h2>
            {badge(loading ? '—' : `${filtered.length} LIGNES`, 'gray')}
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>HEURE</th>
                  <th>NIVEAU</th>
                  <th>SOURCE</th>
                  <th>ÉVÉNEMENT</th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td>
                      <span className="mono">—</span>
                    </td>
                    <td>{badge('—', 'gray')}</td>
                    <td>—</td>
                    <td>{loading ? 'Chargement…' : '—'}</td>
                  </tr>
                ) : (
                  filtered.map((r) => (
                    <tr
                      key={r.key}
                      className="clickable"
                      tabIndex={0}
                      onClick={() => openRow(r.item)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          openRow(r.item)
                        }
                      }}
                    >
                      <td>
                        <span className="mono">{r.time}</span>
                      </td>
                      <td>{badge(r.level)}</td>
                      <td>{r.source}</td>
                      <td>
                        <b>{r.event}</b>
                        {r.item.detail ? <small>{r.item.detail}</small> : null}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="card">
          <div className="card-head">
            <h2>Qualité des données</h2>
          </div>
          <div className="card-body">
            <div className="statline">
              <span>Binance</span>
              <b>
                {loading
                  ? '—'
                  : quality.providerOk
                    ? badge('PASSE')
                    : badge('—', 'gray')}
              </b>
            </div>
            <div className="statline">
              <span>{quality.firstProblem ? displaySymbol(quality.firstProblem.symbol) : '—'}</span>
              <b>
                {quality.firstProblem
                  ? badge('PRUDENCE')
                  : loading
                    ? '—'
                    : badge('PASSE')}
              </b>
            </div>
            <div className="statline">
              <span>Symboles lus</span>
              <b>{loading ? '—' : screener.length}</b>
            </div>
            <div className="statline">
              <span>Bougies manquantes</span>
              <b>
                {loading
                  ? '—'
                  : quality.gapCount > 0
                    ? `${quality.gapCount} actif${quality.gapCount > 1 ? 's' : ''}`
                    : '0'}
              </b>
            </div>
            <p style={{ fontSize: 11, color: 'var(--muted)' }}>
              {quality.problemCount > 0
                ? `${quality.problemCount} symbole${quality.problemCount > 1 ? 's' : ''} avec une bougie périmée ou en retard.`
                : 'Aucune alerte qualité sur le screener.'}
            </p>
          </div>
        </section>
      </div>

      <section className="card">
        <div className="card-head">
          <h2>Ce que le moteur a produit</h2>
        </div>
        <div className="card-body">
          <div className="statline">
            <span>Décisions</span>
            <b>
              {summary
                ? `${summary.decisions.last_24h} sur 24 h · ${summary.decisions.total} au total`
                : '—'}
            </b>
          </div>
          <div className="statline">
            <span>Paper</span>
            <b>
              {summary
                ? `${summary.paper.open_now} ouverte${summary.paper.open_now === 1 ? '' : 's'} · ${summary.paper.closed_total} clôturées`
                : '—'}
            </b>
          </div>
          <div className="statline">
            <span>Trades refusés puis jugés</span>
            <b>
              {summary
                ? `${summary.shadow.blocked_total} refus · ${summary.shadow.judged_total} verdicts`
                : '—'}
            </b>
          </div>
          <div className="statline">
            <span>Campagnes de backtest</span>
            <b>{summary ? String(summary.backtest.runs_total) : '—'}</b>
          </div>
          <div className="statline">
            <span>Preuves mesurées</span>
            <b>
              {summary
                ? `${summary.evidence.measured} / ${summary.evidence.rows_total}`
                : '—'}
            </b>
          </div>
        </div>
      </section>

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
            <div className="dialog-head">
              <h2>
                {displaySymbol(selected.symbol)} · {selected.title}
              </h2>
              <button type="button" onClick={() => setSelected(null)} aria-label="Fermer">
                ×
              </button>
            </div>
            <p>{selected.detail || 'Le journal n’a pas de détail pour cette ligne.'}</p>
            <div className="statline">
              <span>Heure</span>
              <b>{fmtClock(selected.time)}</b>
            </div>
            <div className="statline">
              <span>Portefeuille</span>
              <b>{selected.portfolio || '—'}</b>
            </div>
            {dossierLoading ? <p>Lecture de la décision moteur…</p> : null}
            {dossierError ? <p>{dossierError}</p> : null}
            {dossier ? (
              <>
                <DecisionPipelinePanel view={pipelineFromDecisionDetail(dossier)} />
                <SignalEvidenceCard detail={dossier} />
              </>
            ) : null}
            <div className="dialog-actions">
              <button type="button" className="primary" onClick={() => setSelected(null)}>
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
