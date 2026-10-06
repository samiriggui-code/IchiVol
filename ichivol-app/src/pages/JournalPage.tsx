/**
 * Journal — port littéral de design-reference/ichivol-workspace `journal()` + page-head.
 * Classes HTML = maquette. Données = engine (manquant → « — »).
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
  type ReactNode,
} from 'react'
import { useNavigate } from 'react-router-dom'
import { displaySymbol } from '../lib/markets'
import { labelExitReason } from '../lib/engineTerminology'
import {
  listPaperPortfolios,
  listPaperPositions,
  type PaperPortfolioRow,
  type PaperPosition,
} from '../lib/paper'
import { portfolioLabel } from '../lib/portfolioLabels'
import { BASELINE_PORTFOLIO_CODE, RS_D1_CODE, SESSIONS_CODE } from '../lib/rsPortfolio'
import {
  deleteUserDecision,
  listUserDecisions,
  patchUserDecisionNote,
  patchUserDecisionStatus,
  type UserDecisionRow,
} from '../lib/userDecisions'
import './JournalPage.css'

type JournalTab = 'Trades' | 'Décisions sauvegardées'
type BadgeTone = 'green' | 'amber' | 'red' | 'gray' | ''
type PortfolioFilter = 'Tous' | typeof BASELINE_PORTFOLIO_CODE | typeof SESSIONS_CODE | typeof RS_D1_CODE

const PORTFOLIO_FILTERS: PortfolioFilter[] = ['Tous', BASELINE_PORTFOLIO_CODE, SESSIONS_CODE, RS_D1_CODE]

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

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(+d)) return '—'
  const dd = String(d.getDate()).padStart(2, '0')
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  return `${dd}/${mm} · ${hh}:${mi}`
}

function fmtSens(direction: string | null | undefined): string {
  if (direction === 'LONG') return 'Achat'
  if (direction === 'SHORT') return 'Vente'
  return '—'
}

function fmtR(p: PaperPosition): string {
  const risk = p.risk_amount
  const pnl = p.realized_pnl
  if (risk == null || !Number.isFinite(risk) || risk === 0) return '—'
  if (pnl == null || !Number.isFinite(pnl)) return '—'
  const r = pnl / Math.abs(risk)
  const sign = r > 0 ? '+' : r < 0 ? '−' : ''
  const abs = Math.abs(r).toLocaleString('fr-FR', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })
  return `${sign}${abs}R`
}

function fmtPerf(pnlPct: number | null | undefined): string {
  if (pnlPct == null || !Number.isFinite(pnlPct)) return '—'
  const sign = pnlPct > 0 ? '+' : pnlPct < 0 ? '−' : ''
  const abs = Math.abs(pnlPct).toLocaleString('fr-FR', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })
  return `${sign}${abs} %`
}

function shortExit(reason: string | null | undefined): string {
  return labelExitReason(reason)
}

function downloadCsv(filename: string, headers: string[], rows: string[][]) {
  const esc = (c: string) => `"${c.replace(/"/g, '""')}"`
  const lines = [headers.map(esc).join(','), ...rows.map((r) => r.map(esc).join(','))]
  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function JournalPage() {
  const navigate = useNavigate()
  const [journalTab, setJournalTab] = useState<JournalTab>('Trades')
  const [query, setQuery] = useState('')
  const [trades, setTrades] = useState<PaperPosition[]>([])
  const [portfolioCodeById, setPortfolioCodeById] = useState<Record<string, string>>({})
  const [portfolioFilter, setPortfolioFilter] = useState<PortfolioFilter>('Tous')
  const [decisions, setDecisions] = useState<UserDecisionRow[]>([])
  const [showArchived, setShowArchived] = useState(false)
  const [selectedDecisionId, setSelectedDecisionId] = useState<string | null>(null)
  const [note, setNote] = useState('')
  const [noteSaved, setNoteSaved] = useState(false)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [actionMsg, setActionMsg] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const [closed, rows, portfolios] = await Promise.all([
        listPaperPositions({ status: 'CLOSED' }).catch(() => [] as PaperPosition[]),
        listUserDecisions(80).catch(() => [] as UserDecisionRow[]),
        listPaperPortfolios().catch(() => [] as PaperPortfolioRow[]),
      ])
      setPortfolioCodeById(Object.fromEntries(portfolios.map((p) => [p.id, p.code])))
      setTrades(
        [...closed].sort(
          (a, b) =>
            +new Date(b.exit_time ?? b.entry_time) - +new Date(a.exit_time ?? a.entry_time),
        ),
      )
      setDecisions(rows)
    } catch {
      setTrades([])
      setDecisions([])
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const q = query.trim().toLowerCase()

  const tradePortfolioCode = useCallback(
    (p: PaperPosition): string | null =>
      p.portfolio_id ? (portfolioCodeById[p.portfolio_id] ?? null) : null,
    [portfolioCodeById],
  )

  const visibleTrades = useMemo(() => {
    return trades.filter((p) => {
      if (portfolioFilter !== 'Tous' && tradePortfolioCode(p) !== portfolioFilter) return false
      if (!q) return true
      const base = displaySymbol(p.symbol).toLowerCase()
      return base.includes(q) || p.symbol.toLowerCase().includes(q)
    })
  }, [trades, q, portfolioFilter, tradePortfolioCode])

  const filteredDecisions = useMemo(() => {
    const byStatus = decisions.filter((r) =>
      showArchived ? r.status === 'archived' : r.status === 'confirmed',
    )
    if (!q) return byStatus
    return byStatus.filter((r) => {
      const base = displaySymbol(r.symbol).toLowerCase()
      return base.includes(q) || r.symbol.toLowerCase().includes(q)
    })
  }, [decisions, showArchived, q])

  const selectedDecision = useMemo(
    () => filteredDecisions.find((d) => d.id === selectedDecisionId) ?? filteredDecisions[0] ?? null,
    [filteredDecisions, selectedDecisionId],
  )

  useEffect(() => {
    setNote(selectedDecision?.note ?? '')
    setNoteSaved(false)
  }, [selectedDecision?.id, selectedDecision?.note])

  const replay = useMemo(() => {
    if (journalTab === 'Trades') {
      const t = visibleTrades[0]
      if (!t) return null
      const r = fmtR(t)
      const perf = fmtPerf(t.pnl_pct)
      const result = [r, perf].filter((x) => x !== '—').join(' · ')
      return {
        eyebrow: `${displaySymbol(t.symbol)} · ${fmtDate(t.exit_time ?? t.entry_time).toUpperCase()}`,
        title:
          t.realized_pnl != null && t.realized_pnl > 0
            ? 'Un plan suivi jusqu’à son objectif.'
            : 'Une sortie à relire.',
        body: `${portfolioLabel(tradePortfolioCode(t))} · ${fmtSens(t.direction)} · sortie : ${shortExit(t.exit_reason)}${result ? ` · ${result}` : ''}`,
        symbol: t.symbol,
      }
    }
    const d = selectedDecision
    if (!d) return null
    return {
      eyebrow: `${displaySymbol(d.symbol)} · ${fmtDate(d.createdAt).toUpperCase()}`,
      title: 'Décision sauvegardée.',
      body: d.note?.trim() || '—',
      symbol: d.symbol,
    }
  }, [journalTab, visibleTrades, selectedDecision, tradePortfolioCode])

  const onExport = () => {
    if (journalTab === 'Trades') {
      downloadCsv(
        'journal-trades.csv',
        ['date', 'actif', 'portefeuille', 'sens', 'resultat', 'performance', 'sortie'],
        visibleTrades.map((t) => [
          fmtDate(t.exit_time ?? t.entry_time),
          displaySymbol(t.symbol),
          portfolioLabel(tradePortfolioCode(t)),
          fmtSens(t.direction),
          fmtR(t),
          fmtPerf(t.pnl_pct),
          shortExit(t.exit_reason),
        ]),
      )
      return
    }
    downloadCsv(
      'journal-decisions.csv',
      ['date', 'actif', 'sens', 'statut'],
      filteredDecisions.map((d) => [
        fmtDate(d.createdAt),
        displaySymbol(d.symbol),
        fmtSens(d.bias),
        d.status === 'archived' ? 'ARCHIVÉE' : 'SAUVEGARDÉE',
      ]),
    )
  }

  const onSaveNote = async (e: FormEvent) => {
    e.preventDefault()
    if (!selectedDecision) return
    setBusyId(selectedDecision.id)
    setActionMsg(null)
    try {
      const updated = await patchUserDecisionNote(selectedDecision.id, note)
      setDecisions((prev) => prev.map((r) => (r.id === updated.id ? updated : r)))
      setNote(updated.note ?? '')
      setNoteSaved(true)
      window.setTimeout(() => setNoteSaved(false), 1500)
    } catch (err: unknown) {
      setActionMsg(err instanceof Error ? err.message : 'Note non enregistrée')
    } finally {
      setBusyId(null)
    }
  }

  async function onArchive(row: UserDecisionRow) {
    setBusyId(row.id)
    setActionMsg(null)
    try {
      await patchUserDecisionStatus(row.id, 'archived')
      setDecisions((prev) =>
        prev.map((r) => (r.id === row.id ? { ...r, status: 'archived' } : r)),
      )
      setActionMsg(`${displaySymbol(row.symbol)} · archivée`)
    } catch (err: unknown) {
      setActionMsg(err instanceof Error ? err.message : 'Archivage impossible')
    } finally {
      setBusyId(null)
    }
  }

  async function onRestore(row: UserDecisionRow) {
    setBusyId(row.id)
    setActionMsg(null)
    try {
      await patchUserDecisionStatus(row.id, 'confirmed')
      setDecisions((prev) =>
        prev.map((r) => (r.id === row.id ? { ...r, status: 'confirmed' } : r)),
      )
      setActionMsg(`${displaySymbol(row.symbol)} · restaurée`)
    } catch (err: unknown) {
      setActionMsg(err instanceof Error ? err.message : 'Restauration impossible')
    } finally {
      setBusyId(null)
    }
  }

  async function onDelete(row: UserDecisionRow) {
    if (!window.confirm(`Supprimer définitivement ${displaySymbol(row.symbol)} ?`)) return
    setBusyId(row.id)
    setActionMsg(null)
    try {
      await deleteUserDecision(row.id)
      setDecisions((prev) => prev.filter((r) => r.id !== row.id))
      if (selectedDecisionId === row.id) setSelectedDecisionId(null)
      setActionMsg(`${displaySymbol(row.symbol)} · supprimée`)
    } catch (err: unknown) {
      setActionMsg(err instanceof Error ? err.message : 'Suppression impossible')
    } finally {
      setBusyId(null)
    }
  }

  const openTrade = (symbol: string) => {
    navigate(`/app/market?symbol=${encodeURIComponent(symbol)}`)
  }

  const tableRows =
    journalTab === 'Trades'
      ? visibleTrades.map((t) => {
          const r = fmtR(t)
          const up = r.startsWith('+')
          const down = r.startsWith('−') || r.startsWith('-')
          return (
            <tr
              key={t.id}
              className="clickable"
              tabIndex={0}
              onClick={() => openTrade(t.symbol)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  openTrade(t.symbol)
                }
              }}
            >
              <td>{fmtDate(t.exit_time ?? t.entry_time)}</td>
              <td>
                <b>{displaySymbol(t.symbol)}</b>
              </td>
              <td>{portfolioLabel(tradePortfolioCode(t))}</td>
              <td>{fmtSens(t.direction)}</td>
              <td>
                <span className={`mono${up ? ' up' : down ? ' down' : ''}`.trim()}>{r}</span>
              </td>
              <td>{fmtPerf(t.pnl_pct)}</td>
              <td>{shortExit(t.exit_reason)}</td>
            </tr>
          )
        })
      : filteredDecisions.map((d) => (
          <tr
            key={d.id}
            className={`clickable${selectedDecision?.id === d.id ? ' is-selected' : ''}`.trim()}
            tabIndex={0}
            onClick={() => setSelectedDecisionId(d.id)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                setSelectedDecisionId(d.id)
              }
            }}
          >
            <td>{fmtDate(d.createdAt)}</td>
            <td>
              <b>{displaySymbol(d.symbol)}</b>
            </td>
            <td>{fmtSens(d.bias)}</td>
            <td>
              <div className="journal-decision-actions">
                {badge(d.status === 'archived' ? 'ARCHIVÉE' : 'SAUVEGARDÉE', 'gray')}
                {d.status === 'archived' ? (
                  <button
                    type="button"
                    className="suggestion"
                    disabled={busyId === d.id}
                    onClick={(e) => {
                      e.stopPropagation()
                      void onRestore(d)
                    }}
                  >
                    Restaurer
                  </button>
                ) : (
                  <button
                    type="button"
                    className="suggestion"
                    disabled={busyId === d.id}
                    onClick={(e) => {
                      e.stopPropagation()
                      void onArchive(d)
                    }}
                  >
                    Archiver
                  </button>
                )}
                <button
                  type="button"
                  className="suggestion"
                  disabled={busyId === d.id}
                  onClick={(e) => {
                    e.stopPropagation()
                    void onDelete(d)
                  }}
                >
                  Supprimer
                </button>
              </div>
            </td>
          </tr>
        ))

  const emptyRow = (
    <tr>
      <td colSpan={journalTab === 'Trades' ? 7 : 4} className="muted">
        {journalTab === 'Trades'
          ? 'Aucun trade clôturé pour l’instant.'
          : 'Aucune décision sauvegardée pour l’instant.'}
      </td>
    </tr>
  )

  return (
    <div className="journal-page">
      <div className="page-head">
        <div>
          <div className="eyebrow">06 / ICHIVOL WORKSPACE</div>
          <h1>Journal</h1>
          <p className="subtitle">La mémoire de vos décisions.</p>
        </div>
        <div className="actions">{badge('MÉMOIRE DE TRADING', 'gray')}</div>
      </div>

      <div className="tabs">
        {(['Trades', 'Décisions sauvegardées'] as JournalTab[]).map((t) => (
          <button
            key={t}
            type="button"
            className={journalTab === t ? 'active' : ''}
            onClick={() => setJournalTab(t)}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="toolbar">
        <input
          id="journal-search"
          type="search"
          placeholder="Rechercher un symbole…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {journalTab === 'Trades' && (
          <div className="segmented" role="group" aria-label="Portefeuille">
            {PORTFOLIO_FILTERS.map((f) => (
              <button
                key={f}
                type="button"
                className={portfolioFilter === f ? 'active' : ''}
                onClick={() => setPortfolioFilter(f)}
              >
                {f === 'Tous' ? 'Tous' : portfolioLabel(f)}
              </button>
            ))}
          </div>
        )}
        {journalTab === 'Décisions sauvegardées' && (
          <label className="checkrow" style={{ margin: 0 }}>
            Archivées
            <input
              type="checkbox"
              checked={showArchived}
              onChange={(e) => setShowArchived(e.target.checked)}
            />
          </label>
        )}
        <span style={{ marginLeft: 'auto' }}>
          <button type="button" onClick={onExport}>
            Exporter CSV ↓
          </button>
        </span>
      </div>
      {actionMsg && (
        <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 12 }} role="status">
          {actionMsg}
        </p>
      )}

      <section className="card">
        <div className="card-head">
          <h2>{journalTab}</h2>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              {journalTab === 'Trades' ? (
                <tr>
                  <th>DATE</th>
                  <th>ACTIF</th>
                  <th>PORTEFEUILLE</th>
                  <th>SENS</th>
                  <th>RÉSULTAT</th>
                  <th>PERFORMANCE</th>
                  <th>SORTIE</th>
                </tr>
              ) : (
                <tr>
                  <th>DATE</th>
                  <th>ACTIF</th>
                  <th>SENS</th>
                  <th>STATUT</th>
                </tr>
              )}
            </thead>
            <tbody>{tableRows.length ? tableRows : emptyRow}</tbody>
          </table>
        </div>
      </section>

      <div style={{ height: 20 }} />

      <div className={journalTab === 'Trades' ? '' : 'grid'}>
        <section className="card">
          <div className="card-head">
            <h2>Rejouer une décision</h2>
          </div>
          <div className="card-body">
            {replay ? (
              <>
                <div className="eyebrow">{replay.eyebrow}</div>
                <h3>{replay.title}</h3>
                <p style={{ fontSize: 12, color: 'var(--muted)' }}>{replay.body}</p>
              </>
            ) : (
              <p style={{ fontSize: 12, color: 'var(--muted)' }}>
                {journalTab === 'Trades'
                  ? 'Aucun trade clôturé à rejouer pour ce filtre.'
                  : 'Sélectionnez une décision sauvegardée pour la rejouer.'}
              </p>
            )}
            <button
              type="button"
              className="primary"
              disabled={!replay}
              onClick={() => replay && openTrade(replay.symbol)}
            >
              Ouvrir le détail du trade →
            </button>
          </div>
        </section>

        {journalTab === 'Décisions sauvegardées' && (
        <section className="card">
          <div className="card-head">
            <h2>Note personnelle</h2>
          </div>
          <form className="card-body" id="note-form" onSubmit={(e) => void onSaveNote(e)}>
            <textarea
              id="journal-note"
              rows={4}
              placeholder={
                selectedDecision
                  ? `Note pour ${displaySymbol(selectedDecision.symbol)}…`
                  : 'Sélectionnez une décision pour lui ajouter une note.'
              }
              disabled={!selectedDecision}
              style={{ width: '100%' }}
              value={note}
              onChange={(e) => setNote(e.target.value.slice(0, 500))}
            />
            <div style={{ marginTop: 10 }}>
              <button
                type="submit"
                disabled={!selectedDecision || (busyId != null && busyId === selectedDecision.id)}
              >
                {noteSaved ? 'Enregistrée' : 'Enregistrer la note'}
              </button>
            </div>
          </form>
        </section>
        )}
      </div>
    </div>
  )
}
