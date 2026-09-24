import { useCallback, useEffect, useState } from 'react'
import {
  getPaperOrderDetail,
  listPaperOrders,
  type PaperOrderEventRow,
  type PaperOrderRow,
} from '../lib/paper'
import './OrdersPanel.css'

const STATUS_FILTERS = [
  '',
  'FILLED',
  'CREATED',
  'SUBMITTED',
  'ACK',
  'PARTIAL',
  'CANCELLED',
  'REJECTED',
  'EXPIRED',
  'UNKNOWN',
] as const

function statusClass(status: string): string {
  const s = status.toUpperCase()
  if (s === 'FILLED') return 'is-filled'
  if (s === 'CANCELLED' || s === 'EXPIRED') return 'is-cancel'
  if (s === 'REJECTED') return 'is-reject'
  if (s === 'UNKNOWN') return 'is-unknown'
  if (s === 'PARTIAL') return 'is-partial'
  return 'is-pending'
}

function fmtTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return iso
  return new Date(t).toLocaleString('fr-FR', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

/**
 * T14d — Portefeuille › Ordres : liste + timeline events (lecture seule).
 */
export function OrdersPanel({ portfolioCode = 'ICHIVOL_BASELINE_V1' }: { portfolioCode?: string }) {
  const [status, setStatus] = useState('')
  const [orders, setOrders] = useState<PaperOrderRow[]>([])
  const [divergences, setDivergences] = useState<
    Array<{ name: string; ok: boolean; actual?: unknown }>
  >([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [events, setEvents] = useState<PaperOrderEventRow[]>([])
  const [detailLoading, setDetailLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const page = await listPaperOrders(portfolioCode, {
        status: status || undefined,
        limit: 100,
      })
      setOrders(page.orders)
      setDivergences(page.divergences || [])
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Ordres indisponibles')
    } finally {
      setLoading(false)
    }
  }, [portfolioCode, status])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (!selected) {
      setEvents([])
      return
    }
    let cancelled = false
    setDetailLoading(true)
    getPaperOrderDetail(selected, portfolioCode)
      .then((d) => {
        if (!cancelled) setEvents(d.events)
      })
      .catch(() => {
        if (!cancelled) setEvents([])
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [selected, portfolioCode])

  return (
    <div className="orders-panel">
      {divergences.length > 0 && (
        <div className="orders-divergences" role="status">
          <strong>{divergences.length} divergence{divergences.length > 1 ? 's' : ''}</strong>
          <ul>
            {divergences.map((d) => (
              <li key={d.name}>
                <span className="mono">{d.name}</span>
                {d.actual != null ? ` — ${String(d.actual)}` : ''}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="orders-toolbar">
        <label>
          Statut
          <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Filtrer par statut">
            {STATUS_FILTERS.map((s) => (
              <option key={s || 'all'} value={s}>
                {s || 'Tous'}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="ghost" onClick={() => void load()} disabled={loading}>
          {loading ? '…' : 'Actualiser'}
        </button>
      </div>

      {error && (
        <div className="banner error" role="alert">
          {error}
        </div>
      )}

      <div className="orders-layout">
        <div className="orders-list" role="list">
          {loading && orders.length === 0 ? (
            <p className="muted">Chargement…</p>
          ) : orders.length === 0 ? (
            <p className="muted">Aucun ordre.</p>
          ) : (
            orders.map((o) => (
              <button
                key={o.id}
                type="button"
                role="listitem"
                className={`orders-row${selected === o.id ? ' is-selected' : ''}`}
                onClick={() => setSelected(o.id)}
              >
                <div className="orders-row-top">
                  <strong>{o.symbol.replace(/USDT$/i, '')}</strong>
                  <span className={`iv-badge ${statusClass(o.status)}`}>{o.status}</span>
                </div>
                <div className="orders-row-meta muted">
                  <span>{o.side}</span>
                  <span className="mono">{fmtTime(o.time)}</span>
                  <span className="mono">
                    {o.qty} @ {o.filled_price || o.requested_price}
                  </span>
                </div>
              </button>
            ))
          )}
        </div>

        <aside className="orders-timeline" aria-label="Historique de l’ordre">
          {!selected ? (
            <p className="muted">Sélectionnez un ordre pour voir la timeline.</p>
          ) : detailLoading ? (
            <p className="muted">Timeline…</p>
          ) : events.length === 0 ? (
            <p className="muted">Aucun événement.</p>
          ) : (
            <ol className="orders-events">
              {events.map((e) => (
                <li key={e.seq}>
                  <span className="orders-event-seq mono">{e.seq}</span>
                  <div>
                    <div className="orders-event-path">
                      <span className="mono">{e.from ?? '∅'}</span>
                      <span aria-hidden> → </span>
                      <span className={`iv-badge ${statusClass(e.to)}`}>{e.to}</span>
                    </div>
                    <div className="muted orders-event-meta">
                      {fmtTime(e.at)}
                      {e.reason ? ` · ${e.reason}` : ''}
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </aside>
      </div>
    </div>
  )
}
