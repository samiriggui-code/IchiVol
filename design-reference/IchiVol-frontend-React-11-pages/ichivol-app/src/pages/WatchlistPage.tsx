import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { getDecisionDetail } from '../lib/decisions'
import { decisionPayloadFromDetail } from '../lib/agent'
import { useCopilotNav } from '../lib/useCopilotNav'
import { listWatchlist, removeWatchlistSymbol, type WatchlistRow } from '../lib/watchlist'

/**
 * Watchlist utilisateur = symboles épinglés (pin_symbol Copilot / API).
 * Distinct du Journal (décisions confirmées).
 */
export function WatchlistPage() {
  const [rows, setRows] = useState<WatchlistRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [pendingRemove, setPendingRemove] = useState<WatchlistRow | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const { explainDecision } = useCopilotNav()

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    listWatchlist()
      .then(setRows)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Watchlist indisponible')
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function onExpliquer(row: WatchlistRow) {
    setBusyId(row.id)
    setError(null)
    setInfo(null)
    try {
      const detail = await getDecisionDetail(row.symbol, '1h', false)
      explainDecision(decisionPayloadFromDetail(detail))
      setInfo(`${row.symbol} — ouverture Copilot…`)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Échec chargement décision')
    } finally {
      setBusyId(null)
    }
  }

  async function onRetirer(row: WatchlistRow) {
    setActionError(null)
    setPendingRemove(row)
  }

  async function executeRemove() {
    if (!pendingRemove) return
    const row = pendingRemove
    setBusyId(row.id)
    setError(null)
    setActionError(null)
    try {
      await removeWatchlistSymbol(row.symbol)
      setRows((prev) => prev.filter((r) => r.id !== row.id))
      setInfo(`${row.symbol} retiré de la watchlist`)
      setPendingRemove(null)
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Retrait impossible')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="page-stack">
      <header className="page-head">
        <h1>Watchlist</h1>
        <p className="muted">
          Liste <strong>manuelle</strong> : elle reste vide tant que vous n’avez pas demandé au
          Copilot « ajoute BTC à la watchlist » puis Confirmé. Ce n’est <em>pas</em> le screener
          auto (voir <Link to="/app/decisions">Décisions</Link> /{' '}
          <Link to="/app/paper">Paper</Link>), ni le <Link to="/app/journal">Journal</Link>. L&apos;historique
          de ce que le système fait tout seul est dans <Link to="/app/activite">Activité</Link>.
        </p>
      </header>

      {error && <div className="banner error">{error}</div>}
      {info && <div className="banner">{info}</div>}

      <div className="panel">
        <div className="panel-head" style={{ display: 'flex', justifyContent: 'space-between' }}>
          <h2>Épinglés ({rows.length})</h2>
          <button type="button" className="ghost" onClick={() => load()} disabled={loading}>
            Actualiser
          </button>
        </div>

        {loading && <p className="muted">Chargement…</p>}
        {!loading && rows.length === 0 && (
          <p className="muted">
            Vide — dans le Copilot : « ajoute BTC à la watchlist », puis Confirmer.
          </p>
        )}

        {!loading && rows.length > 0 && (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Symbole</th>
                  <th>Ajouté</th>
                  <th>MAJ</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <strong>{row.symbol.replace(/USDT$/i, '')}</strong>
                      <span className="muted"> {row.symbol}</span>
                    </td>
                    <td>{new Date(row.createdAt).toLocaleString()}</td>
                    <td>{new Date(row.updatedAt).toLocaleString()}</td>
                    <td style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      <button
                        type="button"
                        className="ghost"
                        disabled={busyId === row.id}
                        onClick={() => void onExpliquer(row)}
                      >
                        Expliquer
                      </button>
                      <Link
                        className="ghost"
                        to={`/app/decisions?symbol=${encodeURIComponent(row.symbol)}`}
                      >
                        Décisions
                      </Link>
                      <button
                        type="button"
                        className="ghost"
                        disabled={busyId === row.id}
                        onClick={() => void onRetirer(row)}
                      >
                        Retirer
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {pendingRemove && (
        <ConfirmDialog
          title="Retirer de la watchlist ?"
          body={`Retirer ${pendingRemove.symbol.replace(/USDT$/i, '')} (${pendingRemove.symbol}) de la liste manuelle.`}
          confirmLabel="Retirer"
          confirming={busyId === pendingRemove.id}
          error={actionError}
          onConfirm={() => void executeRemove()}
          onCancel={() => {
            if (!busyId) {
              setPendingRemove(null)
              setActionError(null)
            }
          }}
        />
      )}
    </div>
  )
}
