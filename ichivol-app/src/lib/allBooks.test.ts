/**
 * Vue « Tous les portefeuilles » : additions et verrous combinés.
 */
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { combineEquityCurves, combineLocks, combineOverviews, type Book } from './allBooks'
import type { PaperOverview, PaperPortfolioRow } from './paper'

function book(code: string, equity: number, curve: [string, number][], risk: { cap: number; open: number }): Book {
  const overview = {
    portfolio: { id: code, code, label: code, currency: 'EUR', valuation_mode: 'mark', initial_cash: 5000, cash: 4000, realized_pnl: 0 },
    account: {
      initial_cash: 5000, cash: 4000, invested: 1000, unrealized_pnl: 0, realized_pnl: 0, equity,
      total_pnl: equity - 5000, day_change: null, priced_positions: 1, open_positions: 1,
    },
    positions: [{ id: `${code}-1`, symbol: 'SOLUSDT', status: 'OPEN' }],
    equity_curve: curve.map(([t, e]) => ({ t, equity: e })),
    risk: {
      capital: equity, cash: 4000, exposed: 1000, open_risk_amount: risk.open, open_risk_pct: risk.open / equity,
      max_open_risk_pct: risk.cap, open_positions: 1, max_open_positions: 10, recent_refusals: [], kernel: 'risk_kernel_v1',
    },
  } as unknown as PaperOverview
  return { code, label: code, row: { code } as PaperPortfolioRow, overview }
}

test('les totaux additionnent chaque portefeuille et chaque ligne garde son portefeuille', () => {
  const ov = combineOverviews([
    book('A', 5000, [], { cap: 0.04, open: 50 }),
    book('B', 5000, [], { cap: 0.01, open: 25 }),
  ])!
  assert.equal(ov.account.equity, 10000)
  assert.equal(ov.account.invested, 2000)
  assert.equal(ov.positions.length, 2)
  assert.deepEqual(ov.positions.map((p) => (p as { book_code?: string }).book_code), ['A', 'B'])
  assert.equal(ov.risk!.open_risk_amount, 75)
  // Plafond global = (200 € + 50 €) / 10 000 €, pas le plus grand des deux.
  assert.equal(ov.risk!.max_open_risk_pct, 0.025)
  assert.equal(ov.risk!.max_open_positions, 20)
})

test('la courbe totale garde la dernière valeur connue de chaque portefeuille', () => {
  const curve = combineEquityCurves([
    book('A', 5100, [['2026-10-01T00:00:00Z', 5000], ['2026-10-02T00:00:00Z', 5100]], { cap: 0.04, open: 0 }),
    book('B', 4900, [['2026-10-02T00:00:00Z', 4900]], { cap: 0.04, open: 0 }),
  ])
  // B n'a pas encore de point le 1er : on compte son capital de départ.
  assert.deepEqual(curve.map((p) => p.equity), [10000, 10000])
})

test("l'arrêt d'urgence n'est « armé » que si tous les portefeuilles le sont", () => {
  const rows = [
    { code: 'ICHIVOL_BASELINE_V1', label: 'x', kill_switch_armed: true, daily_loss_locked: false },
    { code: 'ICHIVOL_SESSIONS_V1', label: 'y', kill_switch_armed: false, daily_loss_locked: false },
  ] as PaperPortfolioRow[]
  const partial = combineLocks(rows)
  assert.equal(partial.kill_switch_armed, false)
  assert.equal(partial.entries_blocked, true)
  assert.deepEqual(partial.blocked.map((b) => b.label), ['IchiVol'])
  const all = combineLocks(rows.map((r) => ({ ...r, kill_switch_armed: true })))
  assert.equal(all.kill_switch_armed, true)
})
