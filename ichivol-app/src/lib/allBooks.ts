/**
 * Tous les portefeuilles paper actifs vus ensemble (Desk, Portefeuille « Tous », Opportunités, bandeau d'arrêt).
 * Chaque livre reste calculé par le moteur ; ici on ne fait qu'additionner et étiqueter chaque ligne par son livre.
 */

import {
  getPaperActivity,
  getPaperOverview,
  listPaperPortfolios,
  type PaperCosts,
  type PaperOrderRow,
  type PaperOverview,
  type PaperOverviewPosition,
  type PaperPortfolioRow,
} from './paper'
import type { RiskLockState } from './riskLock'
import { portfolioLabel } from './rsPortfolio'

export const ALL_BOOKS_CODE = 'ALL'

export type BookTag = { book_code: string; book_label: string }
export type BookPosition = PaperOverviewPosition & BookTag
export type BookOrder = PaperOrderRow & BookTag

export type Book = {
  code: string
  label: string
  row: PaperPortfolioRow
  overview: PaperOverview
}

/** Portefeuilles actifs (tous si l'API n'en marque aucun actif). */
export async function listActiveBooks(): Promise<PaperPortfolioRow[]> {
  const rows = await listPaperPortfolios()
  const active = rows.filter((p) => p.is_active !== false)
  return active.length > 0 ? active : rows
}

/** Vue d'ensemble de chaque portefeuille actif ; un livre en erreur est ignoré, pas bloquant. */
export async function loadAllBooks(rows?: PaperPortfolioRow[]): Promise<Book[]> {
  const list = rows ?? (await listActiveBooks())
  const books = await Promise.all(
    list.map((row) =>
      getPaperOverview(row.code)
        .then((overview) => ({ code: row.code, label: portfolioLabel(row.code, row.label), row, overview }))
        .catch(() => null),
    ),
  )
  return books.filter((b): b is Book => b != null)
}

/** Derniers ordres de tous les livres, du plus récent au plus ancien. */
export async function loadAllActivity(
  books: Array<Pick<Book, 'code' | 'label'>>,
  limitPerBook = 50,
): Promise<BookOrder[]> {
  const lists = await Promise.all(
    books.map((b) =>
      getPaperActivity(b.code, limitPerBook)
        .then((orders) => orders.map((o) => ({ ...o, book_code: b.code, book_label: b.label })))
        .catch(() => [] as BookOrder[]),
    ),
  )
  return lists.flat().sort((a, b) => +new Date(b.time) - +new Date(a.time))
}

export function tagPositions(book: Pick<Book, 'code' | 'label' | 'overview'>): BookPosition[] {
  return (book.overview.positions ?? []).map((p) => ({ ...p, book_code: book.code, book_label: book.label }))
}

/** Somme des courbes de capital : chaque livre garde sa dernière valeur connue (son capital de départ avant son premier point). */
export function combineEquityCurves(books: Book[]): { t: string; equity: number }[] {
  const series = books.map((b) => ({
    start: b.overview.account?.initial_cash ?? 0,
    points: (b.overview.equity_curve ?? [])
      .map((p) => ({ ms: +new Date(p.t), equity: p.equity }))
      .filter((p) => Number.isFinite(p.ms) && Number.isFinite(p.equity))
      .sort((a, b) => a.ms - b.ms),
  }))
  const times = [...new Set(series.flatMap((s) => s.points.map((p) => p.ms)))].sort((a, b) => a - b)
  const idx = series.map(() => -1)
  return times.map((ms) => {
    let total = 0
    series.forEach((s, i) => {
      let k = idx[i] ?? -1
      while (k + 1 < s.points.length && s.points[k + 1]!.ms <= ms) k += 1
      idx[i] = k
      total += k >= 0 ? s.points[k]!.equity : s.start
    })
    return { t: new Date(ms).toISOString(), equity: total }
  })
}

function sum(values: Array<number | null | undefined>): number {
  return values.reduce<number>((s, v) => s + (v != null && Number.isFinite(v) ? v : 0), 0)
}

function sumOrNull(values: Array<number | null | undefined>): number | null {
  return values.some((v) => v != null && Number.isFinite(v)) ? sum(values) : null
}

/** Un « portefeuille » qui additionne tous les livres, au format de la vue d'ensemble du moteur. */
export function combineOverviews(books: Book[]): PaperOverview | null {
  if (books.length === 0) return null
  const ovs = books.map((b) => b.overview)
  const accts = ovs.map((o) => o.account)
  const risks = ovs.map((o) => o.risk).filter((r): r is NonNullable<PaperOverview['risk']> => r != null)
  const costs = ovs.map((o) => o.costs).filter((c): c is PaperCosts => c != null)

  const capital = sum(risks.map((r) => r.capital))
  const openRisk = sum(risks.map((r) => r.open_risk_amount))
  // Plafond global = somme des plafonds en euros de chaque livre, rapportée au capital total.
  const capEur = sum(risks.map((r) => (r.max_open_risk_pct != null ? r.max_open_risk_pct * r.capital : null)))

  return {
    portfolio: {
      id: ALL_BOOKS_CODE,
      code: ALL_BOOKS_CODE,
      label: 'Tous les portefeuilles',
      currency: ovs[0]!.portfolio?.currency ?? 'EUR',
      valuation_mode: ovs[0]!.portfolio?.valuation_mode ?? '',
      initial_cash: sum(accts.map((a) => a?.initial_cash)),
      cash: sum(accts.map((a) => a?.cash)),
      realized_pnl: sum(accts.map((a) => a?.realized_pnl)),
    },
    account: {
      initial_cash: sum(accts.map((a) => a?.initial_cash)),
      cash: sum(accts.map((a) => a?.cash)),
      invested: sum(accts.map((a) => a?.invested)),
      unrealized_pnl: sum(accts.map((a) => a?.unrealized_pnl)),
      realized_pnl: sum(accts.map((a) => a?.realized_pnl)),
      equity: sum(accts.map((a) => a?.equity)),
      total_pnl: sum(accts.map((a) => a?.total_pnl)),
      day_change: sumOrNull(accts.map((a) => a?.day_change)),
      priced_positions: sum(accts.map((a) => a?.priced_positions)),
      open_positions: sum(accts.map((a) => a?.open_positions)),
    },
    positions: books.flatMap(tagPositions),
    equity_curve: combineEquityCurves(books),
    costs:
      costs.length > 0
        ? ({
            ...costs[0]!,
            initial_cash: sum(costs.map((c) => c.initial_cash)),
            equity: sum(costs.map((c) => c.equity)),
            gross_result: sum(costs.map((c) => c.gross_result)),
            commissions: sum(costs.map((c) => c.commissions)),
            spread_slippage: sum(costs.map((c) => c.spread_slippage)),
            financing: sum(costs.map((c) => c.financing)),
            total_costs: sum(costs.map((c) => c.total_costs)),
            net_result: sum(costs.map((c) => c.net_result)),
            orders: sum(costs.map((c) => c.orders)),
            notional_traded: sum(costs.map((c) => c.notional_traded)),
            open_positions: sum(costs.map((c) => c.open_positions)),
            invested_now: sum(costs.map((c) => c.invested_now)),
            closed_trades: sum(costs.map((c) => c.closed_trades)),
            wins: sum(costs.map((c) => c.wins)),
            losses: sum(costs.map((c) => c.losses)),
            sum_wins: sum(costs.map((c) => c.sum_wins)),
            sum_losses: sum(costs.map((c) => c.sum_losses)),
            by_market: {},
            note: `Total des ${books.length} portefeuilles.`,
          } satisfies PaperCosts)
        : undefined,
    risk:
      risks.length > 0
        ? {
            capital,
            cash: sum(risks.map((r) => r.cash)),
            exposed: sum(risks.map((r) => r.exposed)),
            open_risk_amount: openRisk,
            open_risk_pct: capital > 0 ? openRisk / capital : null,
            max_open_risk_pct: capital > 0 && capEur > 0 ? capEur / capital : null,
            open_positions: sum(risks.map((r) => r.open_positions)),
            max_open_positions: sum(risks.map((r) => r.max_open_positions)),
            recent_refusals: risks
              .flatMap((r) => r.recent_refusals ?? [])
              .sort((a, b) => +new Date(b.at ?? 0) - +new Date(a.at ?? 0)),
            kernel: risks[0]!.kernel,
          }
        : undefined,
  }
}

export type CombinedLock = RiskLockState & {
  /** Livres dont les entrées sont bloquées, avec la raison. */
  blocked: Array<{ code: string; label: string; kill: boolean; daily: boolean }>
  book_count: number
}

/**
 * Verrou de l'ensemble : « armé » seulement quand TOUS les livres le sont (sinon l'arrêt d'urgence doit encore
 * couper les autres) ; entrées « bloquées » dès qu'un livre l'est.
 */
export function combineLocks(rows: PaperPortfolioRow[]): CombinedLock {
  const blocked = rows
    .filter((r) => r.kill_switch_armed || r.daily_loss_locked)
    .map((r) => ({
      code: r.code,
      label: portfolioLabel(r.code, r.label),
      kill: Boolean(r.kill_switch_armed),
      daily: Boolean(r.daily_loss_locked),
    }))
  return {
    portfolio_code: ALL_BOOKS_CODE,
    kill_switch_armed: rows.length > 0 && rows.every((r) => r.kill_switch_armed),
    kill_switch_armed_at: null,
    daily_loss_locked: rows.some((r) => r.daily_loss_locked),
    daily_loss_locked_at: null,
    entries_blocked: blocked.length > 0,
    blocked,
    book_count: rows.length,
  }
}
