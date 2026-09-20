import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { labelDecision, labelDirection, labelPipelineGate } from '../lib/decisionLabels'
import { getDecisionDetail, type DecisionLabel } from '../lib/decisions'
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

/**
 * Journal utilisateur = confirmations manuelles (Prisma).
 * « Actualiser » sur une ligne = relecture moteur live + mise à jour du snapshot
 * (pour décider de garder en observation ou retirer).
 */
export function JournalPage() {
  const [rows, setRows] = useState<UserDecisionRow[]>([])
  const [instruments, setInstruments] = useState<EngineInstrument[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(null)
  const [showArchived, setShowArchived] = useState(false)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [pendingDelete, setPendingDelete] = useState<UserDecisionRow | null>(null)
  const [pendingArchive, setPendingArchive] = useState<UserDecisionRow | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
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

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    listUserDecisions(80)
      .then(setRows)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Journal indisponible')
      })
      .finally(() => setLoading(false))
  }, [])

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
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Impossible de supprimer')
    } finally {
      setBusyId(null)
    }
  }

  useEffect(() => {
    load()
    getEngineUniverse()
      .then((u) => setInstruments(u.instruments))
      .catch(() => {})
  }, [load])

  const visible = useMemo(
    () =>
      rows.filter((r) => (showArchived ? r.status === 'archived' : r.status === 'confirmed')),
    [rows, showArchived],
  )

  function fmtWhen(iso: string): string {
    return new Date(iso).toLocaleString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  return (
    <div className="journal-page">
      <header className="page-head market-head">
        <div className="market-head-copy">
          <h1>Journal</h1>
          <p className="muted">
            Snapshot de tes décisions confirmées (observation manuelle). Ce n’est pas le compte
            paper — pour le capital voir <Link to="/app/synthese">Synthèse</Link>, pour les
            positions techniques <Link to="/app/paper">Paper</Link>. Le circuit auto est dans{' '}
            <Link to="/app/activite">Activité</Link>.
          </p>
        </div>
        <div className="market-class-tabs" role="tablist" aria-label="Volets journal">
          <button
            type="button"
            role="tab"
            aria-selected={!showArchived}
            className={!showArchived ? 'is-active' : undefined}
            onClick={() => setShowArchived(false)}
          >
            Confirmées
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={showArchived}
            className={showArchived ? 'is-active' : undefined}
            onClick={() => setShowArchived(true)}
          >
            Archivées
          </button>
          <button type="button" onClick={load} disabled={loading}>
            {loading ? '…' : 'Recharger'}
          </button>
        </div>
      </header>

      <section className="panel">
        <header className="panel-head">
          <h2>{showArchived ? 'Archivées' : 'Confirmées'}</h2>
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

        <div className="table-wrap">
          <table>
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
              {visible.map((j) => (
                <tr key={j.id}>
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
                      ? labelPipelineGate(j.gateDecision as 'BUY' | 'SELL' | 'WATCH' | 'NO_TRADE')
                      : '—'}
                  </td>
                  <td className="mono">{j.rvol.toFixed(2)}×</td>
                  <td className="journal-actions">
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
              {!loading && visible.length === 0 && !error && (
                <tr>
                  <td colSpan={8} className="muted center">
                    {showArchived ? (
                      'Aucune entrée archivée.'
                    ) : (
                      <>
                        Vide — sur <Link to="/app/decisions">Décisions</Link>, confirme une ligne.
                      </>
                    )}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

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
