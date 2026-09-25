export interface WatchlistRow {
  id: string
  symbol: string
  note: string | null
  createdAt: string
  updatedAt: string
}

export async function listWatchlist(): Promise<WatchlistRow[]> {
  const res = await fetch('/api/watchlist', { credentials: 'include' })
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { error?: string } | null
    throw new Error(body?.error ?? `Watchlist ${res.status}`)
  }
  const data = (await res.json()) as { rows: WatchlistRow[] }
  return data.rows
}

export async function removeWatchlistSymbol(symbol: string): Promise<void> {
  const res = await fetch(`/api/watchlist/${encodeURIComponent(symbol)}`, {
    method: 'DELETE',
    credentials: 'include',
  })
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { error?: string } | null
    throw new Error(body?.error ?? `Watchlist ${res.status}`)
  }
}
