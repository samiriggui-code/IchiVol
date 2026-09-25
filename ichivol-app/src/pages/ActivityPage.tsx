/**
 * Opérations — port littéral de design-reference/ichivol-workspace `operations()` + page-head.
 * Classes HTML = maquette. Données = engine (manquant → « — »).
 */

import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { getActivityFeed, type ActivityItem, type FeedTone } from '../lib/activity'
import { getScreener, type ScreenerDecisionRow } from '../lib/decisions'
import { displaySymbol } from '../lib/markets'
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
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [f, s] = await Promise.all([
        getActivityFeed(80).catch(() => ({ items: [] as ActivityItem[] })),
        getScreener('1h').catch(() => ({ rows: [] as ScreenerDecisionRow[] })),
      ])
      setFeed(f.items ?? [])
      setScreener(s.rows ?? [])
    } catch {
      setFeed([])
      setScreener([])
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
    }))
  }, [feed])

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
        <div className="actions">{badge('DONNÉES LIVE', 'gray')}</div>
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
            {badge(loading ? '—' : 'LIVE', 'gray')}
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
                    <tr key={r.key} className="clickable">
                      <td>
                        <span className="mono">{r.time}</span>
                      </td>
                      <td>{badge(r.level)}</td>
                      <td>{r.source}</td>
                      <td>{r.event}</td>
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
              <span>Doublons</span>
              <b>—</b>
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
                ? `${quality.problemCount} symbole${quality.problemCount > 1 ? 's' : ''} sous surveillance qualité.`
                : 'Statut issu du screener (T11a).'}
            </p>
          </div>
        </section>
      </div>

      <section className="card">
        <div className="card-head">
          <h2>Ce que la trace explique</h2>
        </div>
        <div className="card-body">
          <div className="grid three" style={{ margin: 0 }}>
            <div>
              <h3>Décision</h3>
              <p style={{ fontSize: 12, color: 'var(--muted)' }}>
                Le signal, ses preuves et son verdict.
              </p>
            </div>
            <div>
              <h3>Protection</h3>
              <p style={{ fontSize: 12, color: 'var(--muted)' }}>
                La règle qui a autorisé ou refusé l’action.
              </p>
            </div>
            <div>
              <h3>Reproductibilité</h3>
              <p style={{ fontSize: 12, color: 'var(--muted)' }}>
                La clôture analysée et la version du moteur.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
