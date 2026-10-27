/**
 * Bilan du portefeuille unique calculé par le moteur :
 * GET /api/engine/paper/portfolios/{code}/breakdown.
 * Performance par décideur et par classe d'actifs, drawdown, règles et univers du compte.
 * Rien n'est recalculé ici : on type la réponse et on formate.
 */

import { MAIN_PORTFOLIO_CODE } from './mainPortfolio'
import type { Decider, DeciderScore } from './decider'

export type BreakdownDecider = 'eve' | 'engine_over_eve' | 'engine' | 'manual'
export type BreakdownAssetClass = 'crypto' | 'forex' | 'metal' | 'index' | 'energy' | 'future' | 'other'

export type BreakdownStats = {
  label: string
  trades: number
  wins: number
  losses: number
  win_rate: number | null
  net: number
  fees: number
  open: number
  avg_win: number | null
  avg_loss: number | null
  sum_wins: number
  sum_losses: number
}

export type DeciderRow = BreakdownStats & { decider: BreakdownDecider }
export type AssetClassRow = BreakdownStats & { asset_class: BreakdownAssetClass | string }

export type BreakdownRules = {
  initial_cash: number
  risk_pct: number
  max_notional_pct: number
  max_open_positions: number
  max_open_risk_pct: number
  daily_loss_limit_pct: number
  allow_short: boolean
  auto_timeframes: string[] | null
  take_profit_r: number | null
  max_friction_bps: number | null
  min_quote_volume_24h: number | null
  filters_mode: string
  decision_windows_mode: string
  engines: string[] | null
  arbitration: string | null
}

export type PortfolioBreakdown = {
  portfolio_code: string
  by_decider: DeciderRow[]
  by_asset_class: AssetClassRow[]
  drawdown: { max_pct: number | null; current_pct: number | null; peak: number | null; last: number | null }
  rules: BreakdownRules
  universe: {
    symbols: Array<{ symbol: string; asset_class: string; friction_bps: number | null }>
    exclusions: Array<{ symbol: string; reason: string }>
  }
}

export async function getPortfolioBreakdown(code = MAIN_PORTFOLIO_CODE): Promise<PortfolioBreakdown> {
  const res = await fetch(`/api/engine/paper/portfolios/${encodeURIComponent(code)}/breakdown`, {
    credentials: 'include',
  })
  if (!res.ok) throw new Error(`Bilan indisponible (${res.status})`)
  return (await res.json()) as PortfolioBreakdown
}

/** Libellés français des classes d'actifs (repli si l'API n'en donne pas). */
export const ASSET_CLASS_FR: Record<string, string> = {
  crypto: 'Crypto',
  forex: 'Forex',
  metal: 'Métaux',
  index: 'Indices',
  energy: 'Énergie',
  future: 'Futures',
  other: 'Autres',
}

export function assetClassLabel(row: Pick<AssetClassRow, 'asset_class' | 'label'>): string {
  return row.label || ASSET_CLASS_FR[row.asset_class] || row.asset_class
}

/** Lignes qui ont au moins un trade clôturé ou une position ouverte (les classes vides n'encombrent pas l'écran). */
export function activeRows<T extends BreakdownStats>(rows: T[]): T[] {
  return rows.filter((r) => r.trades > 0 || r.open > 0)
}

/** Univers groupé par classe d'actifs, dans l'ordre où l'API les rend. */
export function universeByClass(
  symbols: PortfolioBreakdown['universe']['symbols'],
): Array<{ asset_class: string; label: string; symbols: string[] }> {
  const out: Array<{ asset_class: string; label: string; symbols: string[] }> = []
  for (const s of symbols) {
    let g = out.find((x) => x.asset_class === s.asset_class)
    if (!g) {
      g = { asset_class: s.asset_class, label: ASSET_CLASS_FR[s.asset_class] ?? s.asset_class, symbols: [] }
      out.push(g)
    }
    g.symbols.push(s.symbol)
  }
  return out
}

/** Texte français d'un mode « observe » (filtres / fenêtres de sessions suivis sans bloquer). */
export function modeFr(mode: string | null | undefined): string {
  if (mode === 'observe') return 'observation (noté, ne bloque pas)'
  if (mode === 'enforce' || mode === 'block') return 'appliqué (bloque)'
  if (mode === 'off' || !mode) return 'désactivé'
  return mode
}

/** Bilan par décideur du moteur, au format des cartes existantes (DeciderScore), pour les 4 décideurs. */
export function deciderScores(rows: DeciderRow[]): Record<Decider, DeciderScore> {
  const empty = (decider: Decider): DeciderScore => ({
    decider,
    trades: 0,
    wins: 0,
    losses: 0,
    winRate: null,
    net: 0,
    avgWin: null,
    avgLoss: null,
    fees: 0,
    open: 0,
  })
  const out: Record<Decider, DeciderScore> = {
    eve: empty('eve'),
    engine_over_eve: empty('engine_over_eve'),
    engine: empty('engine'),
    manual: empty('manual'),
  }
  for (const r of rows) {
    if (!(r.decider in out)) continue
    out[r.decider] = {
      decider: r.decider,
      trades: r.trades,
      wins: r.wins,
      losses: r.losses,
      winRate: r.win_rate,
      net: r.net,
      avgWin: r.avg_win,
      avgLoss: r.avg_loss,
      fees: r.fees,
      open: r.open,
    }
  }
  return out
}

/** Codes des moteurs qui décident pour le compte (profil moteur), en français. */
const ENGINE_FR: Record<string, string> = {
  scan_1h_ichimoku_rvol: 'scan automatique 1h (Ichimoku × RVOL)',
  eve_autopilot_jev: 'pilote d’Ève avec JEV',
  ordres_manuels: 'ordres manuels',
}

const ARBITRATION_FR: Record<string, string> = {
  un_lot_par_symbole_premier_arrive:
    'un seul lot par symbole : le premier moteur qui ouvre le garde ; les autres sont refusés (« position déjà ouverte ») et ne le retournent pas.',
}

export function enginesFr(codes: string[] | null | undefined): string[] {
  return (codes ?? []).map((c) => ENGINE_FR[c] ?? c)
}

export function arbitrationFr(code: string | null | undefined): string | null {
  if (!code) return null
  return ARBITRATION_FR[code] ?? code
}

/** Fenêtre de session notée à l'entrée d'un lot (entry_signal.decision_event). */
export const SESSION_EVENT_FR: Record<string, string> = {
  tokyo_open: 'ouverture de Tokyo',
  tokyo_close: 'clôture de Tokyo',
  london_open: 'ouverture de Londres',
  london_close: 'clôture de Londres',
  ny_open: 'ouverture de New York',
  ny_close: 'clôture de New York',
}

/** null / absent → « hors fenêtre de session » ; clé inconnue → « session non reconnue » (jamais de JSON brut). */
export function sessionEventFr(event: unknown): string {
  if (event == null || event === '') return 'hors fenêtre de session'
  if (typeof event === 'string') return SESSION_EVENT_FR[event] ?? 'session non reconnue'
  return 'session non reconnue'
}
