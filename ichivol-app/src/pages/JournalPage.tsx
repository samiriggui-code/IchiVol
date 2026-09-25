import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { labelDecision, labelDirection, labelPipelineGate } from '../lib/decisionLabels'
import {
  getDecisionDetail,
  type DecisionDetail,
  type DecisionLabel,
} from '../lib/decisions'
import { decisionPayloadFromDetail } from '../lib/agent'
import { useCopilotNav } from '../lib/useCopilotNav'
import { getEngineUniverse, type EngineInstrument } from '../lib/universe'
import {
  confirmUserDecision,
  deleteUserDecision,
  listUserDecisions,
  patchUserDecisionStatus,
  type UserDecisionRow,
} from '../lib/userDecisions'
import { listPaperPositions, type PaperPosition } from '../lib/paper'
import {
  assetName,
  directionWords,
  exitReasonLabel,
  signedEur,
} from '../lib/tradeStory'
import './JournalPage.css'

const NOTE_MAX = 500

const pctFmt = new Intl.NumberFormat('fr-FR', {
  style: 'percent',
  signDisplay: 'exceptZero',
  maximumFractionDigits: 2,
  minimumFractionDigits: 1,
})

function fmtWhen(iso: string): string {
  return new Date(iso).toLocaleString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function tone(v: number | null | undefined): string {
  if (v == null || v === 0) return ''
  return v > 0 ? 'up' : 'down'
}

function fmtPerf(pnlPct: number | null | undefined): string {
  if (pnlPct == null || !Number.isFinite(pnlPct)) return '—'
  return pctFmt.format(pnlPct)
}

function fmtResultat(p: PaperPosition): string {
  if (p.realized_pnl != null && Number.isFinite(p.realized_pnl)) {
    return signedEur(p.realized_pnl)
  }
  return fmtPerf(p.pnl_pct)
}

function downloadCsv(filename: string, headers: string[], rows: string[][]) {
  const esc = (c: string) => {
    if (/[",\n\r]/.test(c)) return `"${c.replace(/"/g, '""')}"`
    return c
  }
  const lines = [headers.map(esc).join(','), ...rows.map((r) => r.map(esc).join(','))]
  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

/**
 * Journal utilisateur = confirmations manuelles (Prisma) + trades paper fermés.
 * « Actualiser » sur une ligne = relecture moteur live + mise à jour du snapshot.
 */
export function JournalPage() {
  const [rows, setRows] = useState<UserDecisionRow[]>([])
  const [trades, setTrades] = useState<PaperPosition[]>([])
  const [instruments, setInstruments] = useState<EngineInstrument[]>([])
  const [loading, setLoading] = useState(true)
  const [tradesLoading, setTradesLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tradesError, setTradesError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(null)
  const [showArchived, setShowArchived] = useState(false)
  const [journalTab, setJournalTab] = useState<'trades' | 'decisions'>('decisions')
  const [symbolQuery, setSymbolQuery] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)
  const [pendingDelete, setPendingDelete] = useState<UserDecisionRow | null>(null)
  const [pendingArchive, setPendingArchive] = useState<UserDecisionRow | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [noteDraft, setNoteDraft] = useState('')
  const [noteSaving, setNoteSaving] = useState(false)
  const [replayDetail, setReplayDetail] = useState<DecisionDetail | null>(null)
  const [replayLoading, setReplayLoading] = useState(false)
  const [replayError, setReplayError] = useState<string | null>(null)
  const { explainDecision } = useCopilotNav()

  const byId = useMemo(() => {
    const m = new Map<string, EngineInstrument>()
    for (const i of instruments) m.set(i.id, i)
    return m
  }, [instruments])

  const label = useCallback(
    (id: string) => byId.get(id)?.label ?? id.replace(/USDT$/i, ''),
    [byId],
  )

  const loadDecisions = useCallback(() => {
    setLoading(true)
    setError(null)
    listUserDecisions(80)
      .then(setRows)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Journal indisponible')
      })
      .finally(() => setLoading(false))
  }, [])

  const loadTrades = useCallback(() => {
    setTradesLoading(true)
    setTradesError(null)
    listPaperPositions({ status: 'CLOSED' })
      .then((list) =>
        setTrades(
          [...list].sort(
            (a, b) =>
              +new Date(b.exit_time ?? b.entry_time) - +new Date(a.exit_time ?? a.entry_time),
          ),
        ),
      )
      .catch((err: unknown) => {
        setTradesError(err instanceof Error ? err.message : 'Trades indisponibles')
      })
      .finally(() => setTradesLoading(false))
  }, [])

  const load = useCallback(() => {
    loadDecisions()
    loadTrades()
  }, [loadDecisions, loadTrades])

  async function onExpliquer(row: UserDecisionRow) {
    setBusyId(row.id)
    setError(null)
    setInfo(null)
    try {
      const detail = await getDecisionDetail(row.symbol, row.interval, false)
      explainDecision(decisionPayloadFromDetail(detail))
      setInfo(`${row.symbol} — ouverture Copilot…`)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Échec chargement décision')
    } finally {
      setBusyId(null)
    }
  }

  async function onActualiser(row: UserDecisionRow) {
    setBusyId(row.id)
    setError(null)
    setInfo(null)
    try {
      const prevGate = row.gateDecision
      const detail = await getDecisionDetail(row.symbol, row.interval, false)
      const updated = await confirmUserDecision({
        symbol: detail.symbol,
        interval: detail.timeframe,
        bias: detail.direction,
        rvol: detail.rvol ?? 0,
        signalKind: detail.decision,
        gateDecision: detail.pipeline?.decision,
        confidence: detail.confidence,
        note: row.note ?? undefined,
      })
      setRows((prev) => prev.map((r) => (r.id === row.id || r.id === updated.id ? { ...updated } : r)))
      const nextGate = updated.gateDecision ?? detail.pipeline?.decision ?? null
      if (prevGate && nextGate && prevGate !== nextGate) {
        setInfo(
          `${label(row.symbol)} : portes ${prevGate} → ${nextGate}. À toi de garder ou retirer.`,
        )
      } else {
        setInfo(`${label(row.symbol)} : snapshot moteur à jour.`)
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Actualisation impossible')
    } finally {
      setBusyId(null)
    }
  }

  async function onRetirer(id: string) {
    const row = rows.find((r) => r.id === id) ?? null
    if (!row) return
    setActionError(null)
    setPendingArchive(row)
  }

  async function executeArchive() {
    if (!pendingArchive) return
    const id = pendingArchive.id
    setBusyId(id)
    setError(null)
    setInfo(null)
    setActionError(null)
    try {
      await patchUserDecisionStatus(id, 'archived')
      setRows((prev) => prev.map((r) => (r.id === id ? { ...r, status: 'archived' } : r)))
      setPendingArchive(null)
      if (selectedId === id) setSelectedId(null)
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Impossible de retirer')
    } finally {
      setBusyId(null)
    }
  }

  async function onRestaurer(id: string) {
    setBusyId(id)
    setError(null)
    setInfo(null)
    try {
      await patchUserDecisionStatus(id, 'confirmed')
      setRows((prev) => prev.map((r) => (r.id === id ? { ...r, status: 'confirmed' } : r)))
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Impossible de restaurer')
    } finally {
      setBusyId(null)
    }
  }

  async function onSupprimer(id: string) {
    const row = rows.find((r) => r.id === id) ?? null
    if (!row) return
    setActionError(null)
    setPendingDelete(row)
  }

  async function executeDelete() {
    if (!pendingDelete) return
    const id = pendingDelete.id
    setBusyId(id)
    setError(null)
    setInfo(null)
    setActionError(null)
    try {
      await deleteUserDecision(id)
      setRows((prev) => prev.filter((r) => r.id !== id))
      setPendingDelete(null)
      if (selectedId === id) setSelectedId(null)
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Impossible de supprimer')
    } finally {
      setBusyId(null)
    }
  }

  async function onSaveNote(row: UserDecisionRow) {
    setNoteSaving(true)
    setError(null)
    setInfo(null)
    try {
      const note = noteDraft.trim().slice(0, NOTE_MAX)
      const updated = await confirmUserDecision({
        symbol: row.symbol,
        interval: row.interval,
        bias: row.bias,
        rvol: row.rvol,
        signalKind: row.signalKind ?? undefined,
        gateDecision: row.gateDecision ?? undefined,
        confidence: row.confidence ?? undefined,
        note: note || undefined,
      })
      setRows((prev) =>
        prev.map((r) => (r.id === row.id || r.id === updated.id ? { ...updated } : r)),
      )
      setSelectedId(updated.id)
      setNoteDraft(updated.note ?? '')
      setInfo('Note enregistrée.')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Impossible d’enregistrer la note')
    } finally {
      setNoteSaving(false)
    }
  }

  useEffect(() => {
    load()
    getEngineUniverse()
      .then((u) => setInstruments(u.instruments))
      .catch(() => {})
  }, [load])

  const q = symbolQuery.trim().toLowerCase()

  const visibleDecisions = useMemo(() => {
    const base = rows.filter((r) =>
      showArchived ? r.status === 'archived' : r.status === 'confirmed',
    )
    if (!q) return base
    return base.filter((r) => {
      const sym = r.symbol.toLowerCase()
      const lab = label(r.symbol).toLowerCase()
      return (
        sym.includes(q) ||
        lab.includes(q) ||
        sym.replace(/usdt$/, '').includes(q)
      )
    })
  }, [rows, showArchived, q, label])

  const visibleTrades = useMemo(() => {
    if (!q) return trades
    return trades.filter((p) => {
      const sym = p.symbol.toLowerCase()
      const lab = assetName(p.symbol).toLowerCase()
      return (
        sym.includes(q) ||
        lab.includes(q) ||
        sym.replace(/usdt$/, '').includes(q)
      )
    })
  }, [trades, q])

  const tradeCols = useMemo(() => {
    const hasResultat = visibleTrades.some(
      (p) =>
        (p.realized_pnl != null && Number.isFinite(p.realized_pnl)) ||
        (p.pnl_pct != null && Number.isFinite(p.pnl_pct)),
    )
    const hasPerf = visibleTrades.some((p) => p.pnl_pct != null && Number.isFinite(p.pnl_pct))
    const hasExit = visibleTrades.some((p) => Boolean(p.exit_reason))
    return { hasResultat, hasPerf, hasExit }
  }, [visibleTrades])

  const selected = useMemo(
    () => (selectedId ? (rows.find((r) => r.id === selectedId) ?? null) : null),
    [rows, selectedId],
  )

  useEffect(() => {
    if (!selected) {
      setNoteDraft('')
      setReplayDetail(null)
      setReplayError(null)
      return
    }
    setNoteDraft(selected.note ?? '')
    let cancelled = false
    setReplayLoading(true)
    setReplayError(null)
    setReplayDetail(null)
    getDecisionDetail(selected.symbol, selected.interval, false)
      .then((d) => {
        if (!cancelled) setReplayDetail(d)
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setReplayError(err instanceof Error ? err.message : 'Détail indisponible')
        }
      })
      .finally(() => {
        if (!cancelled) setReplayLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [selected])

  function selectDecision(row: UserDecisionRow) {
    setSelectedId((prev) => (prev === row.id ? null : row.id))
  }

  function onExportCsv() {
    if (journalTab === 'trades') {
      const headers = ['date', 'actif', 'sens']
      if (tradeCols.hasResultat) headers.push('resultat')
      if (tradeCols.hasPerf) headers.push('perf')
      if (tradeCols.hasExit) headers.push('motif_sortie')
      const data = visibleTrades.map((p) => {
        const cells = [
          p.exit_time ?? p.entry_time,
          assetName(p.symbol),
          directionWords(p.direction).title,
        ]
        if (tradeCols.hasResultat) cells.push(fmtResultat(p))
        if (tradeCols.hasPerf) cells.push(fmtPerf(p.pnl_pct))
        if (tradeCols.hasExit) cells.push(exitReasonLabel(p.exit_reason))
        return cells
      })
      downloadCsv('journal-trades.csv', headers, data)
      return
    }
    const headers = [
      'confirme',
      'maj',
      'symbole',
      'tf',
      'brut',
      'portes',
      'rvol',
      'note',
      'status',
    ]
    const data = visibleDecisions.map((j) => [
      j.createdAt,
      j.updatedAt ?? '',
      j.symbol,
      j.interval,
      j.signalKind ?? j.bias,
      j.gateDecision ?? '',
      String(j.rvol),
      j.note ?? '',
      j.status,
    ])
    downloadCsv('journal-decisions.csv', headers, data)
  }

  const noteLen = noteDraft.length
  const noteDirty = selected ? noteDraft !== (selected.note ?? '') : false

  return (
    <div className="journal-page">
      <header className="iv-page-header page-head market-head">
        <div className="market-head-copy">
          <p className="iv-page-eyebrow">Recherche · Journal</p>
          <h1>Journal</h1>
          <p className="iv-page-question">
            La mémoire de vos décisions — trades paper et décisions sauvegardées.
          </p>
          <p className="muted">
            Capital → <Link to="/app/portefeuille">Portefeuille</Link> · circuit auto →{' '}
            <Link to="/app/operations">Opérations</Link>.
          </p>
        </div>
        <div className="market-class-tabs" role="tablist" aria-label="Volets journal">
          <button
            type="button"
            role="tab"
            aria-selected={journalTab === 'trades'}
            className={journalTab === 'trades' ? 'is-active' : undefined}
            onClick={() => setJournalTab('trades')}
          >
            Trades
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={journalTab === 'decisions'}
            className={journalTab === 'decisions' ? 'is-active' : undefined}
            onClick={() => setJournalTab('decisions')}
          >
            Décisions sauvegardées
          </button>
          <button
            type="button"
            onClick={load}
            disabled={loading || tradesLoading}
          >
            {loading || tradesLoading ? '…' : 'Recharger'}
          </button>
        </div>
      </header>

      <div className="journal-toolbar" role="search">
        <label>
          <span>Symbole</span>
          <input
            type="search"
            value={symbolQuery}
            onChange={(e) => setSymbolQuery(e.target.value)}
            placeholder="BTC, NEAR…"
            aria-label="Filtrer par symbole"
          />
        </label>
        <button
          type="button"
          className="ghost"
          onClick={onExportCsv}
          disabled={
            journalTab === 'trades'
              ? visibleTrades.length === 0
              : visibleDecisions.length === 0
          }
        >
          Exporter CSV
        </button>
        {journalTab === 'decisions' && (
          <label className="journal-archive-toggle">
            <input
              type="checkbox"
              checked={showArchived}
              onChange={(e) => {
                setShowArchived(e.target.checked)
                setSelectedId(null)
              }}
            />
            <span>Archivées</span>
          </label>
        )}
      </div>

      {journalTab === 'trades' ? (
        <section className="panel">
          <header className="panel-head">
            <h2>Trades paper</h2>
            <span className="muted">Positions fermées</span>
          </header>

          {tradesError && (
            <div className="banner error" role="alert">
              {tradesError}
            </div>
          )}

          {tradesLoading && !trades.length ? (
            <p className="muted journal-empty">Chargement…</p>
          ) : !tradesError && visibleTrades.length === 0 ? (
            <p className="muted journal-empty">
              {trades.length === 0
                ? 'Aucun trade paper fermé pour l’instant.'
                : 'Aucun trade pour ce filtre symbole.'}
            </p>
          ) : (
            <div className="table-wrap">
              <table className="journal-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Actif</th>
                    <th>Sens</th>
                    {tradeCols.hasResultat && <th>Résultat</th>}
                    {tradeCols.hasPerf && <th>Perf</th>}
                    {tradeCols.hasExit && <th>Motif sortie</th>}
                  </tr>
                </thead>
                <tbody>
                  {visibleTrades.map((p) => {
                    const when = p.exit_time ?? p.entry_time
                    const dir = directionWords(p.direction)
                    return (
                      <tr key={p.id}>
                        <td className="mono muted">{fmtWhen(when)}</td>
                        <td>
                          <strong title={p.symbol}>{assetName(p.symbol)}</strong>
                          <span className="muted"> · {p.timeframe}</span>
                        </td>
                        <td>{dir.title}</td>
                        {tradeCols.hasResultat && (
                          <td className={`mono ${tone(p.realized_pnl ?? p.pnl_pct)}`}>
                            {fmtResultat(p)}
                          </td>
                        )}
                        {tradeCols.hasPerf && (
                          <td className={`mono ${tone(p.pnl_pct)}`}>{fmtPerf(p.pnl_pct)}</td>
                        )}
                        {tradeCols.hasExit && (
                          <td className="muted">{exitReasonLabel(p.exit_reason)}</td>
                        )}
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      ) : (
        <>
          <section className="panel">
            <header className="panel-head">
              <h2>{showArchived ? 'Archivées' : 'Décisions sauvegardées'}</h2>
            </header>

            {error && (
              <div className="banner error" role="alert">
                {error}
              </div>
            )}
            {info && !error && (
              <div className="banner" role="status">
                {info}
              </div>
            )}

            {loading && !rows.length ? (
              <p className="muted journal-empty">Chargement…</p>
            ) : (
              <div className="table-wrap">
                <table className="journal-table">
                  <thead>
                    <tr>
                      <th>Confirmé</th>
                      <th>MAJ</th>
                      <th>Symbole</th>
                      <th>TF</th>
                      <th title="Badge combiner (Ichi+RVOL) — diagnostic">Brut</th>
                      <th title="Verdict Portes (pipeline) — action">Portes</th>
                      <th>RVOL</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleDecisions.map((j) => (
                      <tr
                        key={j.id}
                        role="button"
                        tabIndex={0}
                        className={selectedId === j.id ? 'is-selected' : undefined}
                        aria-selected={selectedId === j.id}
                        onClick={() => selectDecision(j)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            selectDecision(j)
                          }
                        }}
                      >
                        <td className="mono muted">{fmtWhen(j.createdAt)}</td>
                        <td className="mono muted">
                          {j.updatedAt ? fmtWhen(j.updatedAt) : '—'}
                        </td>
                        <td>
                          <strong title={j.symbol}>{label(j.symbol)}</strong>
                        </td>
                        <td className="mono">{j.interval}</td>
                        <td>
                          {j.signalKind
                            ? labelDecision(j.signalKind as DecisionLabel)
                            : labelDirection(j.bias as 'LONG' | 'SHORT' | 'NEUTRAL')}
                        </td>
                        <td className="muted">
                          {j.gateDecision
                            ? labelPipelineGate(
                                j.gateDecision as 'BUY' | 'SELL' | 'WATCH' | 'NO_TRADE',
                              )
                            : '—'}
                        </td>
                        <td className="mono">{j.rvol.toFixed(2)}×</td>
                        <td
                          className="journal-actions"
                          onClick={(e) => e.stopPropagation()}
                          onKeyDown={(e) => e.stopPropagation()}
                        >
                          {!showArchived ? (
                            <>
                              <button
                                type="button"
                                className="ghost"
                                disabled={busyId === j.id}
                                onClick={() => void onActualiser(j)}
                                title="Relire le moteur et mettre à jour ce snapshot"
                              >
                                {busyId === j.id ? '…' : 'Actualiser'}
                              </button>
                              <button
                                type="button"
                                className="ghost"
                                disabled={busyId === j.id}
                                onClick={() => void onExpliquer(j)}
                                title="Expliquer cette décision via le Copilot"
                              >
                                Expliquer
                              </button>
                              <button
                                type="button"
                                className="ghost"
                                disabled={busyId === j.id}
                                onClick={() => void onRetirer(j.id)}
                              >
                                Retirer
                              </button>
                              <button
                                type="button"
                                className="ghost"
                                disabled={busyId === j.id}
                                onClick={() => void onSupprimer(j.id)}
                              >
                                Supprimer
                              </button>
                            </>
                          ) : (
                            <>
                              <button
                                type="button"
                                className="ghost"
                                disabled={busyId === j.id}
                                onClick={() => void onRestaurer(j.id)}
                              >
                                Restaurer
                              </button>
                              <button
                                type="button"
                                className="ghost"
                                disabled={busyId === j.id}
                                onClick={() => void onSupprimer(j.id)}
                              >
                                Supprimer
                              </button>
                            </>
                          )}
                        </td>
                      </tr>
                    ))}
                    {!loading && visibleDecisions.length === 0 && !error && (
                      <tr>
                        <td colSpan={8} className="muted center">
                          {showArchived ? (
                            q ? (
                              'Aucune archivée pour ce filtre.'
                            ) : (
                              'Aucune entrée archivée.'
                            )
                          ) : q ? (
                            'Aucune décision pour ce filtre.'
                          ) : (
                            <>
                              Vide — sur <Link to="/app/opportunites">Opportunités</Link>,
                              confirme une ligne.
                            </>
                          )}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {selected && (
            <div className="journal-side">
              <section className="panel journal-note" aria-label="Note personnelle">
                <header className="panel-head">
                  <h2>Note personnelle</h2>
                  <span className="muted">{label(selected.symbol)}</span>
                </header>
                <div style={{ padding: '0 1rem 1rem' }}>
                  <textarea
                    value={noteDraft}
                    maxLength={NOTE_MAX}
                    onChange={(e) => setNoteDraft(e.target.value.slice(0, NOTE_MAX))}
                    placeholder="Contexte, intention, rappel…"
                    aria-label="Note personnelle"
                  />
                  <div className="journal-note-meta">
                    <span className="muted">
                      {noteLen}/{NOTE_MAX}
                    </span>
                    <button
                      type="button"
                      disabled={noteSaving || !noteDirty}
                      onClick={() => void onSaveNote(selected)}
                    >
                      {noteSaving ? '…' : 'Enregistrer'}
                    </button>
                  </div>
                </div>
              </section>

              <section className="panel" aria-label="Rejouer une décision">
                <header className="panel-head">
                  <h2>Rejouer une décision</h2>
                  <span className="muted">
                    {label(selected.symbol)} · {selected.interval}
                  </span>
                </header>
                <div style={{ padding: '0 1rem 1rem' }}>
                  {replayLoading && <p className="muted">Chargement du détail…</p>}
                  {replayError && (
                    <p className="muted" role="alert">
                      {replayError}
                    </p>
                  )}
                  {replayDetail && !replayLoading && (
                    <>
                      <dl className="journal-replay-summary">
                        <dt>Verdict</dt>
                        <dd>
                          {labelDecision(replayDetail.decision)} ·{' '}
                          {labelDirection(replayDetail.direction)}
                          {replayDetail.pipeline?.decision
                            ? ` · portes ${labelPipelineGate(
                                replayDetail.pipeline.decision as
                                  | 'BUY'
                                  | 'SELL'
                                  | 'WATCH'
                                  | 'NO_TRADE',
                              )}`
                            : ''}
                        </dd>
                        <dt>Confiance</dt>
                        <dd className="mono">
                          {pctFmt.format(replayDetail.confidence)}
                          {replayDetail.rvol != null
                            ? ` · RVOL ${replayDetail.rvol.toFixed(2)}×`
                            : ''}
                        </dd>
                        {replayDetail.reasons[0] && (
                          <>
                            <dt>Pourquoi</dt>
                            <dd className="muted">{replayDetail.reasons[0]}</dd>
                          </>
                        )}
                      </dl>
                      <p style={{ marginTop: '0.75rem' }}>
                        <button
                          type="button"
                          className="ghost"
                          disabled={busyId === selected.id}
                          onClick={() => void onExpliquer(selected)}
                        >
                          {busyId === selected.id ? '…' : 'Expliquer'}
                        </button>
                      </p>
                    </>
                  )}
                </div>
              </section>
            </div>
          )}
        </>
      )}

      {pendingDelete && (
        <ConfirmDialog
          title="Supprimer définitivement ?"
          body={`Supprimer le snapshot ${label(pendingDelete.symbol)} du journal. Irréversible — préfère « Retirer » (archive) si tu veux pouvoir restaurer.`}
          confirmLabel="Supprimer"
          danger
          confirming={busyId === pendingDelete.id}
          error={actionError}
          onConfirm={() => void executeDelete()}
          onCancel={() => {
            if (!busyId) {
              setPendingDelete(null)
              setActionError(null)
            }
          }}
        />
      )}

      {pendingArchive && (
        <ConfirmDialog
          title="Retirer du journal ?"
          body={`Archiver ${label(pendingArchive.symbol)} — tu pourras le restaurer depuis les archivés.`}
          confirmLabel="Retirer"
          confirming={busyId === pendingArchive.id}
          error={actionError}
          onConfirm={() => void executeArchive()}
          onCancel={() => {
            if (!busyId) {
              setPendingArchive(null)
              setActionError(null)
            }
          }}
        />
      )}
    </div>
  )
}
