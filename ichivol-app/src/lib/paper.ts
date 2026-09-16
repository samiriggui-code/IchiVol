/** Client Paper trading (engine virtuel — pas de broker réel). */

export type PaperSource = 'auto_watchlist' | 'user_confirmed'
export type PaperStatus = 'OPEN' | 'CLOSED'
export type PaperDirection = 'LONG' | 'SHORT'

export interface PaperPosition {
  id: string
  symbol: string
  timeframe: string
  source: PaperSource | string
  user_id: string | null
  direction: PaperDirection | string
  status: PaperStatus | string
  entry_time: string
  entry_price: number
  entry_decision: string
  exit_time: string | null
  exit_price: number | null
  exit_reason: string | null
  pnl_pct: number | null
}

export interface PaperPerformance {
  num_closed_trades: number
  num_open_positions: number
  total_return: number | null
  win_rate: number | null
  profit_factor: number | null
  expectancy: number | null
  avg_holding_hours: number | null
  best_trade_pct: number | null
  worst_trade_pct: number | null
}

async function parseError(res: Response): Promise<string> {
  const body = (await res.json().catch(() => null)) as
    | { detail?: string; message?: string; error?: string }
    | null
  return body?.detail ?? body?.message ?? body?.error ?? `Erreur ${res.status}`
}

export async function listPaperPositions(opts?: {
  source?: PaperSource
  status?: PaperStatus
}): Promise<PaperPosition[]> {
  const params = new URLSearchParams()
  if (opts?.source) params.set('source', opts.source)
  if (opts?.status) params.set('status', opts.status)
  const q = params.toString()
  const res = await fetch(`/api/engine/paper/positions${q ? `?${q}` : ''}`, {
    credentials: 'include',
  })
  if (!res.ok) throw new Error(await parseError(res))
  const body = (await res.json()) as { positions: PaperPosition[] }
  return body.positions
}

export async function getPaperPerformance(opts?: {
  source?: PaperSource
}): Promise<PaperPerformance> {
  const params = new URLSearchParams()
  if (opts?.source) params.set('source', opts.source)
  const q = params.toString()
  const res = await fetch(`/api/engine/paper/performance${q ? `?${q}` : ''}`, {
    credentials: 'include',
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<PaperPerformance>
}

/** Ouvre une position user_confirmed (user_id injecté par Express). */
export async function openPaperPosition(
  symbol: string,
  timeframe = '1h',
): Promise<PaperPosition> {
  const params = new URLSearchParams({
    symbol,
    timeframe,
  })
  const res = await fetch(`/api/engine/paper/positions?${params}`, {
    method: 'POST',
    credentials: 'include',
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<PaperPosition>
}

export async function closePaperPosition(id: string): Promise<PaperPosition> {
  const res = await fetch(`/api/engine/paper/positions/${encodeURIComponent(id)}/close`, {
    method: 'POST',
    credentials: 'include',
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<PaperPosition>
}
