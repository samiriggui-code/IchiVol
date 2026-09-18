/** Client Paper trading (engine virtuel — pas de broker réel). */

export type PaperSource = 'auto_watchlist' | 'user_confirmed'
export type PaperStatus = 'OPEN' | 'CLOSED'
export type PaperDirection = 'LONG' | 'SHORT'

export interface PaperPosition {
  id: string
  portfolio_id?: string | null
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
  qty?: number | null
  notional?: number | null
  stop_price?: number | null
  take_profit_price?: number | null
  risk_pct?: number | null
  risk_amount?: number | null
  realized_pnl?: number | null
  mfe_pct?: number | null
  mae_pct?: number | null
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
  initial_cash?: number | null
  cash?: number | null
  equity?: number | null
  realized_pnl?: number | null
  unrealized_pnl?: number | null
  max_drawdown?: number | null
  expectancy_eur?: number | null
  valuation_mode?: string | null
}

export interface PaperPortfolioSummary {
  portfolio: {
    id: string
    code: string
    label: string
    currency: string
    valuation_mode: string
    initial_cash: number
    cash: number
    realized_pnl: number
  }
  performance: PaperPerformance
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

export async function getPaperPortfolio(code = 'ICHIVOL_BASELINE_V1'): Promise<PaperPortfolioSummary> {
  const res = await fetch(`/api/engine/paper/portfolios/${encodeURIComponent(code)}`, {
    credentials: 'include',
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<PaperPortfolioSummary>
}

export interface ShadowStats {
  n_total: number
  n_open: number
  n_closed: number
  n_wins: number
  n_losses: number
  win_rate: number | null
  mean_pnl_r: number | null
  filter_verdict: string | null
  by_block_source: Record<string, { n: number; mean_pnl_r: number; wins: number; win_rate?: number }>
  note: string
}

export async function getShadowStats(portfolioCode?: string): Promise<ShadowStats> {
  const q = portfolioCode ? `?portfolio_code=${encodeURIComponent(portfolioCode)}` : ''
  const res = await fetch(`/api/engine/shadow/stats${q}`, { credentials: 'include' })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<ShadowStats>
}
