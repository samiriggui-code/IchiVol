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
  entry_fee?: number | null
  exit_fee?: number | null
  realized_pnl?: number | null
  mfe_pct?: number | null
  mae_pct?: number | null
  /** Lien Evidence Engine / décision source */
  decision_id?: string | null
  evidence_id?: string | null
  entry_signal?: Record<string, unknown> | null
}

export interface OrderIntent {
  actionable: boolean
  reason: string
  symbol: string
  timeframe: string
  pipeline_decision: string
  direction: string | null
  price: number
  stop_distance: number | null
  qty: number | null
  notional: number | null
  entry_fill: number | null
  stop_price: number | null
  take_profit_price: number | null
  risk_pct: number | null
  risk_amount: number | null
  portfolio_code: string
  equity: number | null
  cash: number | null
  volume_type?: string | null
  evidence_summary?: {
    sample_size: number
    sample_quality: string
    status: string
    calibration_note?: string
  } | null
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

/** Ouvre une position user_confirmed (user_id injecté par Express).
 * Idempotent côté engine : si le symbole est déjà OPEN sur le portefeuille
 * baseline, renvoie la position existante avec `already_open: true` (pas de 2ᵉ notional).
 */
export interface ManualOrderInput {
  /** Montant à investir en € (hors frais). */
  notional: number
  /** Distance du stop en fraction du prix (0.02 = 2 %). */
  stopPct: number
  /** Objectif en multiples du risque (2 = gain visé 2× la perte au stop). */
  takeProfitR: number
}

export interface ManualPreview {
  ok: boolean
  blocking: { code: string; message: string }[]
  warnings: { code: string; message: string }[]
  symbol: string
  timeframe: string
  price: number
  engine_verdict: string
  engine_stop_distance: number | null
  inputs: { notional: number; stop_pct: number; stop_distance: number; take_profit_r: number }
  order: {
    qty: number
    entry_fill: number
    notional: number
    stop_price: number
    take_profit_price: number
    risk_amount: number
    risk_pct_of_equity: number | null
  }
  costs: {
    commission_entry: number
    commission_exit_at_target: number
    spread_slippage_entry: number
    round_trip_at_target: number
    commission_bps: number
    friction_bps_per_side: number
  }
  outcomes: { net_gain_if_target: number; net_loss_if_stop: number; reward_risk_net: number | null }
  portfolio: {
    cash_before: number
    cash_after: number
    equity: number
    lines_before: number
    lines_after: number
    max_lines: number
    open_risk_before: number
    open_risk_after: number
    open_risk_cap: number | null
  }
}

/** Aperçu d'un achat choisi par l'utilisateur : coûts, gain/perte nets, effet sur le portefeuille. Ne place rien. */
export async function previewPaperBuy(
  symbol: string,
  timeframe: string,
  order: ManualOrderInput,
  signal?: AbortSignal,
): Promise<ManualPreview> {
  const params = new URLSearchParams({
    symbol,
    timeframe,
    notional: String(order.notional),
    stop_pct: String(order.stopPct),
    take_profit_r: String(order.takeProfitR),
  })
  const res = await fetch(`/api/engine/paper/preview?${params}`, { credentials: 'include', signal })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<ManualPreview>
}

export async function openPaperPosition(
  symbol: string,
  timeframe = '1h',
  order?: ManualOrderInput,
): Promise<PaperPosition & { created?: boolean; already_open?: boolean }> {
  const params = new URLSearchParams({
    symbol,
    timeframe,
  })
  if (order) {
    params.set('discretionary', 'true')
    params.set('notional', String(order.notional))
    params.set('stop_pct', String(order.stopPct))
    params.set('take_profit_r', String(order.takeProfitR))
  }
  const res = await fetch(`/api/engine/paper/positions?${params}`, {
    method: 'POST',
    credentials: 'include',
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<PaperPosition & { created?: boolean; already_open?: boolean }>
}

/** Propose un ordre paper (qty/stop/TP) sans l’ouvrir. */
export async function proposePaperTrade(
  symbol: string,
  timeframe = '1h',
): Promise<OrderIntent> {
  const params = new URLSearchParams({ symbol, timeframe })
  const res = await fetch(`/api/engine/paper/propose?${params}`, {
    credentials: 'include',
  })
  if (!res.ok) throw new Error(await parseError(res))
  const body = (await res.json()) as { intent: OrderIntent }
  return body.intent
}

export async function closePaperPosition(id: string): Promise<PaperPosition> {
  const res = await fetch(`/api/engine/paper/positions/${encodeURIComponent(id)}/close`, {
    method: 'POST',
    credentials: 'include',
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<PaperPosition>
}

export interface PaperPortfolioRow {
  id: string
  code: string
  label: string
  currency: string
  valuation_mode: string
  initial_cash: number
  cash: number
  realized_pnl: number
  is_active: boolean
  started_at: string
  strategy_profile: string
}

export async function listPaperPortfolios(): Promise<PaperPortfolioRow[]> {
  const res = await fetch('/api/engine/paper/portfolios', { credentials: 'include' })
  if (!res.ok) throw new Error(await parseError(res))
  return ((await res.json()) as { portfolios: PaperPortfolioRow[] }).portfolios
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

export type ValuationStatus = 'priced' | 'stale_mark' | 'missing_qty' | 'missing_mark' | 'missing_notional'

export interface PaperOverviewPosition extends PaperPosition {
  current_price: number | null
  unrealized_pnl: number | null
  unrealized_pct: number | null
  price_as_of?: number
  market_value?: number | null
  valuation_status?: ValuationStatus | null
  mark_source?: string | null
  mark_age_s?: number | null
  mark_stale?: boolean | null
}

export interface PaperCosts {
  currency: string
  initial_cash: number
  equity: number
  gross_result: number
  commissions: number
  spread_slippage: number
  financing: number
  total_costs: number
  net_result: number
  net_return_pct: number | null
  cost_share_of_gross_pct: number | null
  orders: number
  notional_traded: number
  open_positions: number
  invested_now: number
  closed_trades: number
  wins: number
  losses: number
  sum_wins: number
  sum_losses: number
  by_market: Record<
    string,
    { commissions: number; friction: number; orders: number; traded: number; total_costs: number }
  >
  note: string
}

export interface PaperProgress {
  days: number
  min_days: number
  closed_trades: number
  min_trades: number
  trades_per_day: number | null
  eta_days_to_min_trades: number | null
  progress_pct: number
  net_realized_closed: number
  top3_gains: number
  net_without_top3: number
  sub_period_net: number[]
  max_drawdown_pct: number
  checks: Record<string, boolean>
  verdict: 'insufficient' | 'candidate' | 'not_retained'
  verdict_label: string
  rules: string
}

export interface PaperOverview {
  portfolio: PaperPortfolioSummary['portfolio']
  account: {
    initial_cash: number
    cash: number
    invested: number
    unrealized_pnl: number
    realized_pnl: number
    equity: number
    liquidation_value?: number
    total_pnl: number
    day_change: number | null
    open_entry_fees?: number
    realized_plus_unrealized?: number
    pnl_explained?: number
    priced_positions: number
    incomplete_open?: number
    stale_open?: number
    open_positions: number
  }
  positions: PaperOverviewPosition[]
  equity_curve: { t: string; equity: number }[]
  costs?: PaperCosts
  progress?: PaperProgress
}

export interface PaperReconcileCheck {
  name: string
  ok: boolean
  expected: unknown
  actual: unknown
  delta: unknown
  positions: string[]
}

export interface PaperReconcileReport {
  portfolio_code: string
  ok: boolean
  anomaly_count: number
  checks: PaperReconcileCheck[]
  equity: number
  liquidation_value: number
  cash: number
}

export async function getPaperOverview(code = 'ICHIVOL_BASELINE_V1'): Promise<PaperOverview> {
  const res = await fetch(`/api/engine/paper/portfolios/${encodeURIComponent(code)}/overview`, {
    credentials: 'include',
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<PaperOverview>
}

export async function getPaperReconcile(code = 'ICHIVOL_BASELINE_V1'): Promise<PaperReconcileReport> {
  const res = await fetch(`/api/engine/paper/portfolios/${encodeURIComponent(code)}/reconcile`, {
    credentials: 'include',
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<PaperReconcileReport>
}

export interface PaperOrderRow {
  id: string
  position_id: string | null
  time: string
  symbol: string
  timeframe: string
  side: 'BUY' | 'SELL' | string
  requested_price: number
  filled_price: number
  qty: number
  notional: number
  fee: number
  status: string
  reason: string | null
}

export async function getPaperActivity(
  code = 'ICHIVOL_BASELINE_V1',
  limit = 100,
): Promise<PaperOrderRow[]> {
  const res = await fetch(
    `/api/engine/paper/portfolios/${encodeURIComponent(code)}/activity?limit=${limit}`,
    { credentials: 'include' },
  )
  if (!res.ok) throw new Error(await parseError(res))
  return ((await res.json()) as { orders: PaperOrderRow[] }).orders
}
