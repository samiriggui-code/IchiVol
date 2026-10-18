/**
 * Journal — poste de trading premium (primitives iv-, voir src/theme/PREMIUM.md).
 * Données = engine (manquant → « — »).
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
} from 'react'
import { useNavigate } from 'react-router-dom'
import { displaySymbol } from '../lib/markets'
import { DECIDER_EXPLAIN, DECIDER_LABEL, DECIDERS, deciderOf, type Decider } from '../lib/decider'
import { labelExitReason } from '../lib/engineTerminology'
import { listPaperPortfolios, listPaperPositions, type PaperPosition } from '../lib/paper'
import { portfolioLabel } from '../lib/rsPortfolio'
import {
  deleteUserDecision,
  listUserDecisions,
  patchUserDecisionNote,
  patchUserDecisionStatus,
  type UserDecisionRow,
} from '../lib/userDecisions'
import './JournalPage.css'

type JournalTab = 'Trades' | 'Décisions sauvegardées'

const NOTE_KEY = 'ichivol-note'

/** Pastille « qui a décidé » au format premium (même libellé et même explication que DeciderBadge). */
function DeciderMark({ decider }: { decider: Decider }) {
  const cls = decider === 'eve' ? ' is-eve' : decider === 'manual' ? ' is-manual' : decider === 'engine_over_eve' ? ' is-vs' : ''
  return (
    <span
      className={`iv-decider${cls}`}
      title={DECIDER_EXPLAIN[decider]}
      aria-label={`${DECIDER_LABEL[decider]} : ${DECIDER_EXPLAIN[decider]}`}
    >
      <i aria-hidden="true" />
      {DECIDER_LABEL[decider]}
    </span>
  )
}

function SideMark({ direction }: { direction: string | null | undefined }) {
  const label = fmtSens(direction)
  if (label === '—') return <span className="dim">—</span>
  if (label === 'Neutre') return <span className="iv-tag is-muted">NEUTRE</span>
  return <span className={`iv-side ${label === 'Vente' ? 'is-short' : 'is-long'}`}>{label.toUpperCase()}</span>
}

function fmtPx(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return '—'
  return n.toLocaleString('fr-FR', { maximumFractionDigits: 6 })
}

function fmtSignedEur(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return ''
  const sign = n > 0 ? '+' : n < 0 ? '−' : ''
  return `${sign}${Math.abs(n).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`
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
  const d = (direction ?? '').toUpperCase()
  if (d === 'LONG' || d === 'BULLISH') return 'Achat'
  if (d === 'SHORT' || d === 'BEARISH') return 'Vente'
  if (d === 'NEUTRAL') return 'Neutre'
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
  const [deciderFilter, setDeciderFilter] = useState<Decider | 'all'>('all')
  const [trades, setTrades] = useState<PaperPosition[]>([])
  /** id du portefeuille → nom court : chaque trade du journal dit de quel portefeuille il vient. */
  const [bookLabels, setBookLabels] = useState<ReadonlyMap<string, string>>(() => new Map())
  const [decisions, setDecisions] = useState<UserDecisionRow[]>([])
  const [showArchived, setShowArchived] = useState(false)
  const [selectedDecisionId, setSelectedDecisionId] = useState<string | null>(null)
  const [note, setNote] = useState('')
  const [noteSaved, setNoteSaved] = useState(false)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [actionMsg, setActionMsg] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const [closed, rows, pfs] = await Promise.all([
        listPaperPositions({ status: 'CLOSED' }).catch(() => [] as PaperPosition[]),
        listUserDecisions(80).catch(() => [] as UserDecisionRow[]),
        listPaperPortfolios().catch(() => []),
      ])
      setBookLabels(new Map(pfs.map((p) => [p.id, portfolioLabel(p.code, p.label)])))
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

  const visibleTrades = useMemo(() => {
    const byDecider = deciderFilter === 'all' ? trades : trades.filter((p) => deciderOf(p) === deciderFilter)
    if (!q) return byDecider
    return byDecider.filter((p) => {
      const base = displaySymbol(p.symbol).toLowerCase()
      const book = (p.portfolio_id ? bookLabels.get(p.portfolio_id) : '')?.toLowerCase() ?? ''
      return base.includes(q) || p.symbol.toLowerCase().includes(q) || book.includes(q)
    })
  }, [trades, q, bookLabels, deciderFilter])

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
      const t = visibleTrades[0] ?? trades[0]
      if (!t) return null
      return {
        eyebrow: `${displaySymbol(t.symbol)} · ${fmtDate(t.exit_time ?? t.entry_time).toUpperCase()}`,
        title:
          t.realized_pnl != null && t.realized_pnl > 0
            ? 'Un plan suivi jusqu’à son objectif.'
            : 'Une sortie à relire.',
        body: '—',
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
  }, [journalTab, visibleTrades, trades, selectedDecision])

  const onExport = () => {
    if (journalTab === 'Trades') {
      downloadCsv(
        'journal-trades.csv',
        ['date', 'actif', 'decideur', 'sens', 'resultat', 'performance', 'sortie'],
        visibleTrades.map((t) => [
          fmtDate(t.exit_time ?? t.entry_time),
          displaySymbol(t.symbol),
          DECIDER_LABEL[deciderOf(t)],
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
      ['date', 'actif', 'sens', 'resultat', 'performance', 'sortie'],
      filteredDecisions.map((d) => [
        fmtDate(d.createdAt),
        displaySymbol(d.symbol),
        fmtSens(d.bias),
        '—',
        '—',
        d.status === 'archived' ? 'ARCHIVÉE' : 'SAUVEGARDÉE',
      ]),
    )
  }

  const onSaveNote = async (e: FormEvent) => {
    e.preventDefault()
    if (!selectedDecision) {
      try {
        localStorage.setItem(NOTE_KEY, note)
        setNoteSaved(true)
        window.setTimeout(() => setNoteSaved(false), 1500)
      } catch {
        /* ignore */
      }
      return
    }
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

  const replayTrade = journalTab === 'Trades' ? (visibleTrades[0] ?? trades[0] ?? null) : null
  const bookOf = (t: PaperPosition) => (t.portfolio_id ? bookLabels.get(t.portfolio_id) : undefined)

  const tableRows =
    journalTab === 'Trades'
      ? visibleTrades.map((t) => {
          const r = fmtR(t)
          const up = r.startsWith('+')
          const down = r.startsWith('−') || r.startsWith('-')
          const perfCls = t.pnl_pct == null ? '' : t.pnl_pct > 0 ? 'pos' : t.pnl_pct < 0 ? 'neg' : ''
          return (
            <tr
              key={t.id}
              className={`jr-click${replayTrade?.id === t.id ? ' is-selected' : ''}`}
              tabIndex={0}
              title="Voir sur le graphique"
              onClick={() => openTrade(t.symbol)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  openTrade(t.symbol)
                }
              }}
            >
              <td className="mono dim">{fmtDate(t.exit_time ?? t.entry_time)}</td>
              <td className="sym">{displaySymbol(t.symbol)}</td>
              <td>
                <SideMark direction={t.direction} />
              </td>
              <td>{bookOf(t) ?? <span className="dim">—</span>}</td>
              <td>
                <DeciderMark decider={deciderOf(t)} />
              </td>
              <td className="n">{fmtPx(t.entry_price)}</td>
              <td className="n">{fmtPx(t.exit_price)}</td>
              <td className={`n${up ? ' pos' : down ? ' neg' : ''}`}>
                {r}
                {t.realized_pnl != null ? <span className="jr-sub"> · {fmtSignedEur(t.realized_pnl)}</span> : null}
              </td>
              <td className={`n ${perfCls}`.trim()}>{fmtPerf(t.pnl_pct)}</td>
              <td className="muted">{shortExit(t.exit_reason)}</td>
            </tr>
          )
        })
      : filteredDecisions.map((d) => (
          <tr
            key={d.id}
            className={`jr-click${selectedDecision?.id === d.id ? ' is-selected' : ''}`.trim()}
            tabIndex={0}
            onClick={() => setSelectedDecisionId(d.id)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                setSelectedDecisionId(d.id)
              }
            }}
          >
            <td className="mono dim">{fmtDate(d.createdAt)}</td>
            <td className="sym">
              {displaySymbol(d.symbol)}
              <small>{d.interval ? d.interval.toUpperCase() : ''}</small>
            </td>
            <td>
              <SideMark direction={d.bias} />
            </td>
            <td className="n dim">—</td>
            <td className="n dim">—</td>
            <td className="jr-note-cell">{d.note?.trim() ? d.note : <span className="dim">—</span>}</td>
            <td>
              <div className="jr-actions">
                <span className={`iv-tag ${d.status === 'archived' ? 'is-muted' : 'is-cyan'}`}>
                  {d.status === 'archived' ? 'Archivée' : 'Sauvegardée'}
                </span>
                {d.status === 'archived' ? (
                  <button
                    type="button"
                    className="iv-btn iv-btn--sm"
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
                    className="iv-btn iv-btn--sm"
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
                  className="iv-btn iv-btn--sm iv-btn--ghost jr-danger"
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

  const toolsLabel =
    journalTab === 'Trades'
      ? `${visibleTrades.length} trade${visibleTrades.length > 1 ? 's' : ''} clôturé${visibleTrades.length > 1 ? 's' : ''}`
      : `${filteredDecisions.length} décision${filteredDecisions.length > 1 ? 's' : ''}${showArchived ? ' archivée' + (filteredDecisions.length > 1 ? 's' : '') : ''}`

  return (
    <div className="journal-page">
      <div className="iv-ph">
        <div>
          <div className="iv-meta">Journal · mémoire de trading</div>
          <h1>Journal</h1>
          <p>La mémoire de vos décisions : qui a décidé, ce qui s’est passé, ce que vous en retenez.</p>
        </div>
        <div className="iv-ph-act jr-toolbar">
          {journalTab === 'Trades' ? (
            <select
              className="iv-input"
              aria-label="Qui a décidé le trade"
              value={deciderFilter}
              onChange={(e) => setDeciderFilter(e.target.value as Decider | 'all')}
            >
              <option value="all">Tous les décideurs</option>
              {DECIDERS.map((d) => (
                <option key={d} value={d}>
                  {DECIDER_LABEL[d]}
                </option>
              ))}
            </select>
          ) : (
            <label className="iv-chip jr-check">
              <input
                className="iv-check"
                type="checkbox"
                checked={showArchived}
                onChange={(e) => setShowArchived(e.target.checked)}
              />
              Archivées
            </label>
          )}
          <input
            id="journal-search"
            className="iv-input jr-search"
            type="search"
            placeholder="Rechercher un symbole…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button type="button" className="iv-btn" onClick={onExport}>
            Exporter CSV
          </button>
        </div>
      </div>

      {actionMsg && (
        <p className="iv-note jr-status" role="status">
          {actionMsg}
        </p>
      )}

      <div className="iv-grid">
        <section className="iv-card iv-s8 iv-m-s12 jr-main">
          <div className="iv-card-head">
            <div className="iv-card-tabs" role="tablist" aria-label="Journal">
              {(['Trades', 'Décisions sauvegardées'] as JournalTab[]).map((t) => (
                <button
                  key={t}
                  type="button"
                  role="tab"
                  aria-selected={journalTab === t}
                  className={`iv-card-tab${journalTab === t ? ' is-on' : ''}`}
                  onClick={() => setJournalTab(t)}
                >
                  {t}
                </button>
              ))}
            </div>
            <div className="iv-card-tools">{toolsLabel}</div>
          </div>
          {tableRows.length === 0 ? (
            <div className="iv-empty">
              {journalTab === 'Trades'
                ? q || deciderFilter !== 'all'
                  ? 'Aucun trade clôturé ne correspond à ce filtre.'
                  : 'Aucun trade clôturé pour l’instant.'
                : 'Aucune décision sauvegardée.'}
            </div>
          ) : (
            <div className="iv-card-body is-flush iv-table-wrap">
              <table className="iv-table">
                <thead>
                  {journalTab === 'Trades' ? (
                    <tr>
                      <th>Date</th>
                      <th>Actif</th>
                      <th>Sens</th>
                      <th>Portefeuille</th>
                      <th>Qui a décidé</th>
                      <th className="n">Entrée</th>
                      <th className="n">Sortie</th>
                      <th className="n">Résultat</th>
                      <th className="n">Performance</th>
                      <th>Sortie par</th>
                    </tr>
                  ) : (
                    <tr>
                      <th>Date</th>
                      <th>Actif</th>
                      <th>Sens</th>
                      <th className="n">Résultat</th>
                      <th className="n">Performance</th>
                      <th>Note</th>
                      <th>Statut</th>
                    </tr>
                  )}
                </thead>
                <tbody>{tableRows}</tbody>
              </table>
            </div>
          )}
        </section>

        <div className="iv-s4 iv-m-s12 jr-side">
          <section className="iv-card iv-glow">
            <div className="iv-card-head">
              <div className="iv-card-tabs">
                <span className="iv-card-tab is-on">Rejouer une décision</span>
              </div>
              <div className="iv-card-tools">{replay?.eyebrow ?? '—'}</div>
            </div>
            <div className="iv-card-body">
              <h3 className="jr-replay-title">{replay?.title ?? '—'}</h3>
              {replayTrade ? (
                <p className="iv-note jr-replay">
                  <DeciderMark decider={deciderOf(replayTrade)} />
                  {bookOf(replayTrade) ? ` · ${bookOf(replayTrade)}` : ''} · {fmtSens(replayTrade.direction)} à{' '}
                  {fmtPx(replayTrade.entry_price)}, sortie à {fmtPx(replayTrade.exit_price)}.{' '}
                  <span className={fmtR(replayTrade).startsWith('+') ? 'pos' : fmtR(replayTrade).startsWith('−') ? 'neg' : ''}>
                    {shortExit(replayTrade.exit_reason)} · {fmtR(replayTrade)}
                    {replayTrade.realized_pnl != null ? ` (${fmtSignedEur(replayTrade.realized_pnl)})` : ''}
                  </span>
                </p>
              ) : (
                <p className="iv-note jr-replay">{replay?.body ?? '—'}</p>
              )}
              <button
                type="button"
                className="iv-btn iv-btn--primary"
                disabled={!replay}
                onClick={() => replay && openTrade(replay.symbol)}
              >
                Voir sur le graphique →
              </button>
            </div>
          </section>

          <section className="iv-card">
            <div className="iv-card-head">
              <div className="iv-card-tabs">
                <span className="iv-card-tab is-on">Note personnelle</span>
              </div>
              <div className="iv-card-tools">
                {selectedDecision ? displaySymbol(selectedDecision.symbol) : 'Session'}
              </div>
            </div>
            <form className="iv-card-body" id="note-form" onSubmit={(e) => void onSaveNote(e)}>
              <textarea
                id="journal-note"
                className="iv-input jr-note"
                rows={4}
                placeholder={
                  selectedDecision
                    ? `Note pour ${displaySymbol(selectedDecision.symbol)}…`
                    : 'Ce que je retiens de cette session…'
                }
                value={note}
                onChange={(e) => setNote(e.target.value.slice(0, 500))}
              />
              <div className="jr-note-foot">
                <button
                  type="submit"
                  className="iv-btn iv-btn--sm"
                  disabled={busyId != null && busyId === selectedDecision?.id}
                >
                  {noteSaved ? 'Enregistrée' : 'Enregistrer la note'}
                </button>
                {noteSaved ? <span className="iv-chip is-mint">Enregistrée</span> : null}
                <span className="iv-cap jr-count">{note.length} / 500</span>
              </div>
            </form>
          </section>
        </div>
      </div>
    </div>
  )
}
