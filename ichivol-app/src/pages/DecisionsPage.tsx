/**
 * Opportunités — port littéral de design-reference/ichivol-workspace `opportunites()` + page-head.
 * Classes HTML = maquette. Données = engine (pas de démo inventée ; manquant → « — »).
 * Fiche décision : FicheDecision via shell `?fiche=decision:SYM:tf` (plus de dialog local).
 */

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import { DATA_REFRESH_EVENT } from '../lib/actionFeedback'
import { getScreener, type ScreenerDecisionRow } from '../lib/decisions'
import { normalizeFicheSymbol } from '../lib/ficheDeepLink'
import { displaySymbol } from '../lib/markets'
import { useFicheNav } from '../lib/useFicheNav'
import {
  maquetteGateBadge,
  type MaquetteBadgeTone,
} from './market/marketMaquetteHelpers'
import './DecisionsPage.css'

type OppFilter = 'Tous' | 'WATCH' | 'ARMED' | 'TRIGGERED'

type CycleLabel = 'WATCH' | 'ARMED' | 'TRIGGERED' | 'ACCEPTÉ' | 'REFUSÉ' | '—'

function badge(text: string, tone: MaquetteBadgeTone | string = ''): ReactNode {
  let inferred = tone
  if (!inferred) {
    inferred = /PASSE|ACCEPTÉ|OUVERTE|VALIDÉ|TRIGGERED/i.test(text)
      ? 'green'
      : /REFUS|BLOQU|ERREUR|ÉCHEC/i.test(text)
        ? 'red'
        : /PRUDENCE|ARMED|WATCH/i.test(text)
          ? 'amber'
          : ''
  }
  return <span className={`tag ${inferred}`.trim()}>{text}</span>
}

function cycleFromRow(row: ScreenerDecisionRow): CycleLabel {
  const gate = row.pipeline?.decision?.toUpperCase?.() ?? ''
  if (gate === 'BUY' || gate === 'SELL') return 'TRIGGERED'
  if (gate === 'WATCH') return 'ARMED'
  if (gate === 'NO_TRADE') return 'WATCH'
  const d = String(row.decision || '').toUpperCase()
  if (d === 'STRONG_BUY' || d === 'STRONG_SELL' || d === 'BUY' || d === 'SELL') return 'TRIGGERED'
  if (d === 'WATCH') return 'ARMED'
  if (d === 'WAIT') return 'WATCH'
  return '—'
}

function stageBadge(row: ScreenerDecisionRow, stageId: string): ReactNode {
  const stages = row.pipeline?.stages
  const st = stages?.find((s) => s.id === stageId)
  if (!st) return badge('—', 'gray')
  const b = maquetteGateBadge(st.status)
  if (b.text === 'ÉCHEC') return badge('BLOQUÉ', 'red')
  return badge(b.text, b.tone)
}

function participationBadge(row: ScreenerDecisionRow): ReactNode {
  if (row.pipeline?.stages?.some((s) => s.id === 'participation')) {
    return stageBadge(row, 'participation')
  }
  if (row.rvol == null || !Number.isFinite(row.rvol)) return badge('—', 'gray')
  return row.rvol >= 1.5 ? badge('PASSE') : badge('PRUDENCE', 'amber')
}

function directionCell(row: ScreenerDecisionRow): ReactNode {
  if (row.direction === 'SHORT' || row.decision === 'SELL' || row.decision === 'STRONG_SELL') {
    return <span className="down">↓ Vente</span>
  }
  if (row.direction === 'LONG' || row.decision === 'BUY' || row.decision === 'STRONG_BUY') {
    return <span className="up">↑ Achat</span>
  }
  return <span>—</span>
}

function confidencePct(row: ScreenerDecisionRow): string {
  if (row.confidence == null || !Number.isFinite(row.confidence)) return '—'
  return `${Math.round(row.confidence * 100)}`
}

export function DecisionsPage() {
  const [searchParams] = useSearchParams()
  const { openDecisionFiche } = useFicheNav()
  const [rows, setRows] = useState<ScreenerDecisionRow[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [oppFilter, setOppFilter] = useState<OppFilter>('Tous')
  const legacyHandled = useRef<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await getScreener('1h')
      setRows(res.rows ?? [])
    } catch {
      setRows([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    const onRefresh = () => {
      void load()
    }
    window.addEventListener(DATA_REFRESH_EVENT, onRefresh)
    return () => window.removeEventListener(DATA_REFRESH_EVENT, onRefresh)
  }, [load])

  // Compat : ?symbol= / ?open=1 → ?fiche=decision:SYM:1h (+ tab=plan si open)
  useEffect(() => {
    if (searchParams.get('fiche')) return
    const raw = searchParams.get('symbol')
    if (!raw) return
    const sym = normalizeFicheSymbol(raw)
    if (!sym) return
    const openPlan = searchParams.get('open') === '1'
    const key = `${sym}|${openPlan ? 'plan' : 'view'}`
    if (legacyHandled.current === key) return
    legacyHandled.current = key
    openDecisionFiche(sym, '1h', {
      tab: openPlan ? 'plan' : 'synthese',
      replace: true,
    })
  }, [searchParams, openDecisionFiche])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return rows.filter((r) => {
      const cycle = cycleFromRow(r)
      if (oppFilter !== 'Tous' && cycle !== oppFilter) return false
      if (!q) return true
      const base = displaySymbol(r.symbol).toLowerCase()
      const full = r.symbol.toLowerCase()
      return base.includes(q) || full.includes(q)
    })
  }, [rows, query, oppFilter])

  const whyRow = useMemo(() => {
    const triggered = rows.filter((r) => cycleFromRow(r) === 'TRIGGERED')
    const pool = triggered.length ? triggered : rows
    if (!pool.length) return null
    return [...pool].sort((a, b) => (b.confidence ?? 0) - (a.confidence ?? 0))[0] ?? null
  }, [rows])

  const whyBase = whyRow ? displaySymbol(whyRow.symbol) : '—'
  const whyCycle = whyRow ? cycleFromRow(whyRow) : '—'

  return (
    <div className="opps-page">
      <div className="page-head">
        <div>
          <div className="eyebrow">03 / ICHIVOL WORKSPACE</div>
          <h1>Opportunités</h1>
          <p className="subtitle">Chaque décision commence par une preuve.</p>
        </div>
        <div className="actions">{badge('DONNÉES LIVE', 'gray')}</div>
      </div>

      <div className="toolbar">
        <input
          type="search"
          id="opp-search"
          placeholder="Rechercher un actif…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div className="segmented">
          {(['Tous', 'WATCH', 'ARMED', 'TRIGGERED'] as OppFilter[]).map((t) => (
            <button
              key={t}
              type="button"
              className={oppFilter === t ? 'active' : ''}
              onClick={() => setOppFilter(t)}
            >
              {t}
            </button>
          ))}
        </div>
        <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--muted)' }}>
          {loading ? '—' : `${filtered.length} actifs`} · clôture 1H
        </span>
      </div>

      <section className="card">
        <div className="card-head">
          <h2>Matrice de décision</h2>
          {badge('5 PORTES', 'gray')}
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ACTIF</th>
                <th>DIRECTION</th>
                <th>PARTICIPATION</th>
                <th>STRUCTURE</th>
                <th>EMPLACEMENT</th>
                <th>RÉGIME</th>
                <th>CYCLE</th>
                <th>CONFIANCE</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={8}>
                    <b>—</b>
                    <small>{loading ? 'Chargement…' : 'Aucune ligne'}</small>
                  </td>
                </tr>
              ) : (
                filtered.map((r) => {
                  const base = displaySymbol(r.symbol)
                  const cycle = cycleFromRow(r)
                  return (
                    <tr
                      key={r.symbol}
                      className="clickable"
                      tabIndex={0}
                      onClick={() => openDecisionFiche(r.symbol, r.timeframe || '1h')}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          openDecisionFiche(r.symbol, r.timeframe || '1h')
                        }
                      }}
                    >
                      <td>
                        <b>{base}</b>
                        <small>{base} · USDT</small>
                      </td>
                      <td>{directionCell(r)}</td>
                      <td>{participationBadge(r)}</td>
                      <td>{stageBadge(r, 'structure')}</td>
                      <td>{stageBadge(r, 'location')}</td>
                      <td>{stageBadge(r, 'regime')}</td>
                      <td>{badge(cycle === '—' ? '—' : cycle)}</td>
                      <td>
                        <span className="mono">{confidencePct(r)} %</span>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </section>

      <div style={{ height: 20 }} />

      <div className="grid">
        <section className="card">
          <div className="card-head">
            <h2>De l’observation à la décision</h2>
          </div>
          <div className="card-body">
            <div className="toolbar">
              {(['WATCH', 'ARMED', 'TRIGGERED', 'ACCEPTÉ', 'REFUSÉ'] as const).map((s, i) => (
                <span key={s}>
                  {i ? ' → ' : ''}
                  {badge(s)}
                </span>
              ))}
            </div>
            <p style={{ fontSize: 12, color: 'var(--muted)' }}>
              Un signal traverse chaque contrôle. La confiance complète la lecture ; elle ne
              remplace jamais le verdict du Risk Kernel.
            </p>
          </div>
        </section>

        <section className="card">
          <div className="card-head">
            <h2>{whyRow ? `Pourquoi ${whyBase} ?` : 'Pourquoi — ?'}</h2>
            {badge(whyCycle === '—' ? '—' : whyCycle)}
          </div>
          <div className="card-body">
            <p style={{ fontSize: 12 }}>
              {whyRow
                ? 'Direction, volume et structure lus par le moteur. Le plan attend une validation finale du risque.'
                : '—'}
            </p>
            {whyRow ? (
              <button
                type="button"
                className="primary"
                onClick={() =>
                  openDecisionFiche(whyRow.symbol, whyRow.timeframe || '1h')
                }
              >
                Ouvrir la fiche de décision →
              </button>
            ) : (
              <button type="button" className="primary" disabled>
                —
              </button>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}
