import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { KeenIcon } from './KeenIcon'
import { IconBell } from './NavIcons'
import {
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  type AppNotification,
  type NotificationKind,
} from '../lib/notifications'

function fmtWhen(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const diff = (Date.now() - d.getTime()) / 1000
  if (diff < 60) return 'à l’instant'
  if (diff < 3600) return `il y a ${Math.floor(diff / 60)} min`
  if (diff < 86400) return `il y a ${Math.floor(diff / 3600)} h`
  return d.toLocaleString('fr-FR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
}

function kindMeta(kind: NotificationKind | string): {
  icon: string
  label: string
  tone: 'journal' | 'pipeline' | 'system' | 'position' | 'default'
} {
  switch (kind) {
    case 'journal_confirm':
      return { icon: 'notepad', label: 'Journal', tone: 'journal' }
    case 'pipeline_change':
      return { icon: 'pulse', label: 'Pipeline', tone: 'pipeline' }
    case 'system_alert':
      return { icon: 'shield-cross', label: 'Système', tone: 'system' }
    case 'system_digest':
      return { icon: 'chart-line', label: 'Résumé', tone: 'system' }
    case 'position_target_near':
    case 'position_stop_near':
    case 'position_accel':
    case 'position_direction_flip':
      return { icon: 'notification', label: 'Position', tone: 'position' }
    default:
      return { icon: 'notification-bing', label: 'Info', tone: 'default' }
  }
}

function payloadSymbol(n: AppNotification): string | null {
  const s = n.payload?.symbol
  return typeof s === 'string' && s.length > 0 ? s : null
}

function payloadInterval(n: AppNotification): string | null {
  const s = n.payload?.interval
  return typeof s === 'string' && s.length > 0 ? s : null
}

export function NotificationBell({ onOpen }: { onOpen?: () => void }) {
  const navigate = useNavigate()
  const rootRef = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const [rows, setRows] = useState<AppNotification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async (opts?: { silent?: boolean }) => {
    if (!opts?.silent) setLoading(true)
    setError(null)
    try {
      const res = await listNotifications({ limit: 30 })
      setRows(res.rows)
      setUnreadCount(res.unreadCount)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erreur notifs')
    } finally {
      if (!opts?.silent) setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
    const id = window.setInterval(() => void refresh({ silent: true }), 60_000)
    return () => window.clearInterval(id)
  }, [refresh])

  useEffect(() => {
    if (open) void refresh({ silent: rows.length > 0 })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refresh on open only
  }, [open])

  useEffect(() => {
    if (!open) return
    function onDoc(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDoc)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  function onOpenToggle() {
    setOpen((v) => {
      const next = !v
      if (next) onOpen?.()
      return next
    })
  }

  async function onActivate(n: AppNotification) {
    if (!n.readAt) {
      try {
        await markNotificationRead(n.id)
        setRows((prev) =>
          prev.map((r) => (r.id === n.id ? { ...r, readAt: new Date().toISOString() } : r)),
        )
        setUnreadCount((c) => Math.max(0, c - 1))
      } catch {
        /* ignore mark failure — still navigate */
      }
    }

    const symbol = payloadSymbol(n)
    const positionId =
      typeof n.payload?.positionId === 'string' ? n.payload.positionId : null
    setOpen(false)
    if (
      positionId ||
      n.kind === 'position_target_near' ||
      n.kind === 'position_stop_near' ||
      n.kind === 'position_accel' ||
      n.kind === 'position_direction_flip'
    ) {
      const q = new URLSearchParams()
      if (symbol) q.set('symbol', symbol)
      if (positionId) q.set('position', positionId)
      const interval = payloadInterval(n)
      if (interval) q.set('interval', interval)
      navigate(`/app/portefeuille?tab=positions&${q.toString()}`)
      return
    }
    if (symbol) {
      const interval = payloadInterval(n)
      const q = new URLSearchParams({ symbol })
      if (interval) q.set('interval', interval)
      navigate(`/app/opportunites?${q.toString()}`)
      return
    }
    if (n.kind === 'journal_confirm') navigate('/app/journal')
  }

  async function onReadAll() {
    try {
      await markAllNotificationsRead()
      setRows((prev) => prev.map((r) => ({ ...r, readAt: r.readAt ?? new Date().toISOString() })))
      setUnreadCount(0)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Échec')
    }
  }

  return (
    <div className="dash-popover-wrap" ref={rootRef}>
      <button
        type="button"
        className={`dash-icon-btn dash-bell-btn${unreadCount > 0 ? ' has-unread' : ''}`}
        aria-label={
          unreadCount > 0 ? `Notifications (${unreadCount} non lues)` : 'Notifications'
        }
        aria-expanded={open}
        onClick={onOpenToggle}
      >
        <IconBell />
        {unreadCount > 0 && (
          <span className="dash-bell-badge" aria-hidden>
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="dash-popover dash-notif-popover" role="dialog" aria-label="Notifications">
          <header className="dash-notif-head">
            <div className="dash-notif-head-title">
              <span className="dash-notif-head-icon" aria-hidden>
                <KeenIcon icon="notification-bing" style="duotone" />
              </span>
              <div>
                <strong>Notifications</strong>
                <span className="dash-notif-head-sub muted">
                  {unreadCount > 0 ? `${unreadCount} non lue${unreadCount > 1 ? 's' : ''}` : 'À jour'}
                </span>
              </div>
            </div>
            <div className="dash-notif-head-actions">
              {unreadCount > 0 && (
                <button type="button" className="ghost" onClick={() => void onReadAll()}>
                  Tout lu
                </button>
              )}
              <Link to="/app/journal" className="ghost" onClick={() => setOpen(false)}>
                Journal
              </Link>
            </div>
          </header>

          {error && <p className="banner error dash-notif-error">{error}</p>}

          {loading && rows.length === 0 ? (
            <div className="dash-notif-empty">
              <p className="muted">Chargement…</p>
            </div>
          ) : rows.length === 0 ? (
            <div className="dash-notif-empty">
              <span className="dash-notif-empty-icon" aria-hidden>
                <KeenIcon icon="verify" style="duotone" />
              </span>
              <p>Aucune notification</p>
              <span className="muted">
                Les confirms journal et les changements de portes apparaîtront ici.
              </span>
            </div>
          ) : (
            <ul className="dash-notif-list">
              {rows.map((n) => {
                const meta = kindMeta(n.kind)
                const symbol = payloadSymbol(n)
                const interval = payloadInterval(n)
                return (
                  <li key={n.id} className={n.readAt ? undefined : 'is-unread'}>
                    <button
                      type="button"
                      className="dash-notif-item"
                      onClick={() => void onActivate(n)}
                    >
                      <span className={`dash-notif-kind dash-notif-kind--${meta.tone}`} aria-hidden>
                        <KeenIcon icon={meta.icon} style="duotone" />
                      </span>
                      <span className="dash-notif-main">
                        <span className="dash-notif-row">
                          <span className="dash-notif-title">{n.title}</span>
                          {!n.readAt && <span className="dash-notif-dot" aria-label="Non lue" />}
                        </span>
                        <span className="dash-notif-body">{n.body}</span>
                        <span className="dash-notif-meta muted">
                          <span className="dash-notif-chip">{meta.label}</span>
                          {symbol && <span className="dash-notif-chip mono">{symbol}</span>}
                          {interval && <span className="dash-notif-chip">{interval}</span>}
                          <span className="dash-notif-when">{fmtWhen(n.createdAt)}</span>
                        </span>
                      </span>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
