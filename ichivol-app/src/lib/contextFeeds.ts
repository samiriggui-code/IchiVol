/** Client context news + calendar (engine V3) — lecture seule, jamais un vote. */

export interface ContextNewsItem {
  title: string
  url: string
  source: string
  published_at: number | null
}

export interface ContextCalendarEvent {
  title: string
  country: string
  date: string
  impact: string
  forecast: string | null
  previous: string | null
}

async function parseError(res: Response): Promise<string> {
  const body = (await res.json().catch(() => null)) as
    | { detail?: string; error?: string; message?: string }
    | null
  return body?.detail ?? body?.error ?? body?.message ?? `Erreur ${res.status}`
}

export async function fetchContextNews(opts?: {
  limit?: number
  sources?: string[]
}): Promise<ContextNewsItem[]> {
  const params = new URLSearchParams()
  params.set('limit', String(opts?.limit ?? 20))
  if (opts?.sources && opts.sources.length > 0) {
    params.set('sources', opts.sources.join(','))
  }
  const res = await fetch(`/api/engine/context/news?${params}`, { credentials: 'include' })
  if (!res.ok) throw new Error(await parseError(res))
  const body = (await res.json()) as { items?: ContextNewsItem[] }
  return Array.isArray(body.items) ? body.items : []
}

export async function fetchContextCalendar(opts?: {
  limit?: number
}): Promise<ContextCalendarEvent[]> {
  const params = new URLSearchParams()
  if (opts?.limit != null) params.set('limit', String(opts.limit))
  const q = params.toString()
  const res = await fetch(`/api/engine/context/calendar${q ? `?${q}` : ''}`, {
    credentials: 'include',
  })
  if (!res.ok) throw new Error(await parseError(res))
  const body = (await res.json()) as { events?: ContextCalendarEvent[] }
  return Array.isArray(body.events) ? body.events : []
}
