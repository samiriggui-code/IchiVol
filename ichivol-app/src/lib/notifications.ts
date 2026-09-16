export type NotificationKind = 'journal_confirm' | 'pipeline_change'

export interface AppNotification {
  id: string
  userId: string
  kind: NotificationKind | string
  title: string
  body: string
  payload: Record<string, unknown> | null
  readAt: string | null
  createdAt: string
}

export interface NotificationsResponse {
  rows: AppNotification[]
  unreadCount: number
}

async function parseError(res: Response): Promise<string> {
  const body = (await res.json().catch(() => null)) as { error?: string } | null
  return body?.error ?? `Erreur ${res.status}`
}

export async function listNotifications(opts?: {
  unread?: boolean
  limit?: number
}): Promise<NotificationsResponse> {
  const params = new URLSearchParams()
  if (opts?.unread) params.set('unread', '1')
  if (opts?.limit) params.set('limit', String(opts.limit))
  const q = params.toString()
  const res = await fetch(`/api/notifications${q ? `?${q}` : ''}`, { credentials: 'include' })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<NotificationsResponse>
}

export async function markNotificationRead(id: string): Promise<AppNotification> {
  const res = await fetch(`/api/notifications/${encodeURIComponent(id)}/read`, {
    method: 'POST',
    credentials: 'include',
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<AppNotification>
}

export async function markAllNotificationsRead(): Promise<void> {
  const res = await fetch('/api/notifications/read-all', {
    method: 'POST',
    credentials: 'include',
  })
  if (!res.ok) throw new Error(await parseError(res))
}
